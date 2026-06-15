//! Built-in web UI — a hand-rolled HTTP server on std::net only (no framework,
//! no extra crates), so the exe stays self-contained. Serves a config page and
//! a small JSON API to edit config, start/stop/pause the loops, read a bar, and
//! calibrate a box. One thread per connection (fine for a single local user).

use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};

use crate::calibrate;
use crate::capture::{red_percentage, Capturer};
use crate::config;
use crate::watch;

struct Rt {
    stop: Arc<AtomicBool>,
    paused: Arc<AtomicBool>,
    handles: Mutex<Vec<JoinHandle<()>>>,
    running: AtomicBool,
}

pub fn serve(port: u16) {
    let rt = Arc::new(Rt {
        stop: Arc::new(AtomicBool::new(false)),
        paused: Arc::new(AtomicBool::new(false)),
        handles: Mutex::new(Vec::new()),
        running: AtomicBool::new(false),
    });
    let listener = match TcpListener::bind(("127.0.0.1", port)) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("could not bind 127.0.0.1:{port}: {e}");
            return;
        }
    };
    println!("cleric-rs UI -> http://127.0.0.1:{port}  (Ctrl+C to quit)");
    for stream in listener.incoming().flatten() {
        let rt = rt.clone();
        thread::spawn(move || handle(stream, rt));
    }
}

fn handle(mut stream: TcpStream, rt: Arc<Rt>) {
    let peek = match stream.try_clone() {
        Ok(s) => s,
        Err(_) => return,
    };
    let mut reader = BufReader::new(peek);

    let mut request_line = String::new();
    if reader.read_line(&mut request_line).is_err() {
        return;
    }
    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or("");
    let target = parts.next().unwrap_or("/");

    let mut content_length = 0usize;
    loop {
        let mut line = String::new();
        if reader.read_line(&mut line).is_err() {
            break;
        }
        let t = line.trim_end();
        if t.is_empty() {
            break;
        }
        let lower = t.to_ascii_lowercase();
        if let Some(v) = lower.strip_prefix("content-length:") {
            content_length = v.trim().parse().unwrap_or(0);
        }
    }
    let mut body_bytes = vec![0u8; content_length];
    if content_length > 0 {
        let _ = reader.read_exact(&mut body_bytes);
    }
    let body = String::from_utf8_lossy(&body_bytes).to_string();

    let (path, query) = target.split_once('?').unwrap_or((target, ""));

    match (method, path) {
        ("GET", "/") => respond(&mut stream, 200, "text/html; charset=utf-8", INDEX_HTML),

        ("GET", "/api/config") => {
            let cfg = config::load();
            let json = serde_json::to_string(&cfg).unwrap_or_else(|_| "{}".into());
            respond(&mut stream, 200, "application/json", &json);
        }

        ("POST", "/api/config") => match serde_json::from_str::<config::Config>(&body) {
            Ok(cfg) => match config::save(&cfg) {
                Ok(()) => respond(&mut stream, 200, "application/json", "{\"ok\":true}"),
                Err(e) => respond(&mut stream, 500, "application/json", &err_json(&e.to_string())),
            },
            Err(e) => respond(&mut stream, 400, "application/json", &err_json(&e.to_string())),
        },

        ("GET", "/api/logs") => {
            let since = query_get(query, "since").and_then(|s| s.parse().ok()).unwrap_or(0);
            let (total, lines) = crate::log::since(since);
            let arr = lines
                .iter()
                .map(|l| format!("\"{}\"", json_escape(l)))
                .collect::<Vec<_>>()
                .join(",");
            respond(&mut stream, 200, "application/json", &format!("{{\"total\":{total},\"lines\":[{arr}]}}"));
        }

        ("GET", "/api/status") => {
            let json = format!(
                "{{\"running\":{},\"paused\":{}}}",
                rt.running.load(Ordering::Relaxed),
                rt.paused.load(Ordering::Relaxed)
            );
            respond(&mut stream, 200, "application/json", &json);
        }

        ("POST", "/api/start") => {
            start(&rt);
            respond(&mut stream, 200, "application/json", "{\"ok\":true}");
        }
        ("POST", "/api/stop") => {
            stop(&rt);
            respond(&mut stream, 200, "application/json", "{\"ok\":true}");
        }
        ("POST", "/api/pause") => {
            let now = !rt.paused.load(Ordering::Relaxed);
            rt.paused.store(now, Ordering::Relaxed);
            crate::log::log(if now { "[run] paused" } else { "[run] resumed" });
            respond(&mut stream, 200, "application/json", &format!("{{\"paused\":{now}}}"));
        }

        ("GET", "/api/read") => {
            let name = query_get(query, "name").unwrap_or_else(|| config::load().default_guy);
            let pct = read_pct(&name);
            respond(
                &mut stream,
                200,
                "application/json",
                &format!("{{\"name\":\"{}\",\"pct\":{:.2}}}", json_escape(&name), pct),
            );
        }

        ("POST", "/api/calibrate") => {
            let name = query_get(query, "name").unwrap_or_default();
            if name.is_empty() {
                respond(&mut stream, 400, "application/json", &err_json("name required"));
                return;
            }
            match crate::draw::draw_box() {
                Some((l, t, w, h)) => match calibrate::save_box(&name, l, t, w, h) {
                    Ok(pct) => respond(
                        &mut stream,
                        200,
                        "application/json",
                        &format!(
                            "{{\"ok\":true,\"name\":\"{}\",\"left\":{l},\"top\":{t},\"width\":{w},\"height\":{h},\"pct\":{pct:.1}}}",
                            json_escape(&name)
                        ),
                    ),
                    Err(e) => respond(&mut stream, 500, "application/json", &err_json(&e)),
                },
                None => respond(&mut stream, 200, "application/json", &err_json("cancelled or box too small")),
            }
        }

        _ => respond(&mut stream, 404, "text/plain", "not found"),
    }
}

fn start(rt: &Arc<Rt>) {
    if rt.running.load(Ordering::Relaxed) {
        return;
    }
    let cfg = config::load();
    rt.stop.store(false, Ordering::Relaxed);
    rt.paused.store(false, Ordering::Relaxed);
    let h1 = watch::run_health_loop(cfg.clone(), rt.stop.clone(), rt.paused.clone());
    let h2 = watch::run_log_tail(cfg.clone(), rt.stop.clone(), rt.paused.clone());
    *rt.handles.lock().unwrap() = vec![h1, h2];
    rt.running.store(true, Ordering::Relaxed);
    crate::log::log("[run] started");
}

fn stop(rt: &Arc<Rt>) {
    if !rt.running.load(Ordering::Relaxed) {
        return;
    }
    rt.stop.store(true, Ordering::Relaxed);
    let handles: Vec<_> = rt.handles.lock().unwrap().drain(..).collect();
    for h in handles {
        let _ = h.join();
    }
    rt.running.store(false, Ordering::Relaxed);
    crate::log::log("[run] stopped");
}

fn read_pct(name: &str) -> f32 {
    let cfg = config::load();
    if let Some(b) = cfg.bounding_boxes.get(name) {
        if let Some(cap) = Capturer::new() {
            if let Some(buf) = cap.grab(b.left as i32, b.top as i32, b.width as i32, b.height as i32) {
                return red_percentage(&buf, b.width as i32, b.height as i32);
            }
        }
    }
    0.0
}

fn respond(stream: &mut TcpStream, status: u16, ctype: &str, body: &str) {
    let reason = match status {
        200 => "OK",
        400 => "Bad Request",
        404 => "Not Found",
        500 => "Internal Server Error",
        _ => "OK",
    };
    let header = format!(
        "HTTP/1.1 {status} {reason}\r\nContent-Type: {ctype}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    let _ = stream.write_all(header.as_bytes());
    let _ = stream.write_all(body.as_bytes());
    let _ = stream.flush();
}

fn err_json(msg: &str) -> String {
    format!("{{\"ok\":false,\"error\":\"{}\"}}", json_escape(msg))
}

fn json_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"").replace('\n', " ")
}

fn query_get(query: &str, key: &str) -> Option<String> {
    for pair in query.split('&') {
        if let Some((k, v)) = pair.split_once('=') {
            if k == key {
                return Some(url_decode(v));
            }
        }
    }
    None
}

fn url_decode(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'+' => {
                out.push(b' ');
                i += 1;
            }
            b'%' if i + 2 < bytes.len() => {
                let h = u8::from_str_radix(&s[i + 1..i + 3], 16).unwrap_or(b'%');
                out.push(h);
                i += 3;
            }
            c => {
                out.push(c);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).to_string()
}

const INDEX_HTML: &str = r##"<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>cleric</title>
<style>
:root{--bg:#0f1216;--card:#181c22;--line:#262c34;--fg:#e6e9ee;--muted:#8b95a3;--accent:#5b9dff;--good:#46d17e;--warn:#f3c969;--bad:#ff6b6b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,Arial}
.wrap{max-width:820px;margin:0 auto;padding:20px 16px 60px}
header{display:flex;align-items:center;gap:12px;margin-bottom:16px}
header h1{font-size:18px;margin:0;font-weight:600;letter-spacing:.3px}
.pill{padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;background:#2a2f37;color:var(--muted)}
.pill.on{background:rgba(70,209,126,.18);color:var(--good)}
.pill.pause{background:rgba(243,201,105,.18);color:var(--warn)}
.spacer{flex:1}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.card h2{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin:0 0 12px}
button{font:inherit;font-weight:600;padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:#222831;color:var(--fg);cursor:pointer}
button:hover{border-color:#3a4250}
button.primary{background:var(--accent);border-color:var(--accent);color:#06101f}
button.danger{color:var(--bad)}
.controls{display:flex;gap:8px;flex-wrap:wrap}
.hp{display:flex;align-items:baseline;gap:10px;margin-bottom:8px}
.hp .name{color:var(--muted)} .hp .val{font-size:30px;font-weight:700}
.bar{height:16px;background:#0c0f13;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.bar>i{display:block;height:100%;width:0;background:var(--good);transition:width .4s,background .4s}
label{display:block;margin:10px 0 3px;font-size:12px;color:var(--muted)}
input,textarea{width:100%;padding:8px;border-radius:7px;border:1px solid var(--line);background:#11151a;color:var(--fg);font:inherit}
textarea{height:74px;resize:vertical} .row{display:flex;gap:12px;flex-wrap:wrap} .row>div{flex:1;min-width:140px}
.chk{display:flex;align-items:center;gap:8px;margin-top:10px} .chk input{width:auto}
#log{background:#0a0d11;border:1px solid var(--line);border-radius:8px;height:240px;overflow:auto;padding:10px;font:12px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap}
#log div{color:#c2c9d4} #log .heal{color:var(--good)} #log .warn{color:var(--warn)} #log .err{color:var(--bad)}
#msg{min-height:18px;color:var(--accent);margin-top:8px;font-size:13px} #msg.err{color:var(--bad)}
pre{background:#11151a;border:1px solid var(--line);border-radius:7px;padding:10px;overflow:auto;font-size:12px;color:var(--muted)}
</style></head><body><div class="wrap">

<header>
 <h1>cleric</h1>
 <span id="status" class="pill">stopped</span>
 <span class="spacer"></span>
 <div class="controls">
  <button class="primary" onclick="api('start')">Start</button>
  <button onclick="api('pause')">Pause</button>
  <button class="danger" onclick="api('stop')">Stop</button>
 </div>
</header>

<div class="card">
 <h2>Live</h2>
 <div class="hp"><span class="name" id="hpname">-</span><span class="val" id="hpval">-</span></div>
 <div class="bar"><i id="hpbar"></i></div>
 <div id="msg"></div>
</div>

<div class="card">
 <h2>Activity log</h2>
 <div id="log"></div>
</div>

<div class="card">
 <h2>Settings</h2>
 <label>Log file path</label><input id="log_file">
 <div class="row">
  <div><label>Default guy</label><input id="default_guy"></div>
  <div><label>Stop-heal log phrase</label><input id="stop_heal_log"></div>
 </div>
 <div class="row">
  <div><label>Heal binding</label><input id="heal_binding"></div>
  <div><label>Heal threshold %</label><input type="number" id="heal_threshold"></div>
  <div><label>Duck-check secs</label><input type="number" step="0.1" id="heal_duck_check_time"></div>
 </div>
 <div class="row">
  <div><label>CH binding</label><input id="ch_binding"></div>
  <div><label>CH threshold %</label><input type="number" id="ch_threshold"></div>
 </div>
 <label class="chk"><input type="checkbox" id="verbose"> verbose (log every HP read and raw log lines)</label>
 <label>Match words (one per line; a line containing "go" triggers Complete Heal)</label>
 <textarea id="match_words"></textarea>
 <label>Word bindings (one per line: phrase = key, e.g. assist me = shift+x)</label>
 <textarea id="word_bindings"></textarea>
 <div style="margin-top:12px"><button class="primary" onclick="save()">Save settings</button></div>
</div>

<div class="card">
 <h2>Bounding boxes</h2>
 <pre id="boxes"></pre>
 <label>Add / recalibrate a box - a dim overlay appears, drag a rectangle over the bar</label>
 <div class="row">
  <div><input id="box_name" placeholder="name e.g. tank"></div>
  <div style="flex:0"><button onclick="calibrate()">Calibrate</button></div>
 </div>
</div>

<script>
const $=id=>document.getElementById(id);
let cfg={}, logSeen=0;
function msg(t,e){const m=$('msg');m.textContent=t||'';m.className=e?'err':'';}
async function jget(u){return (await fetch(u)).json();}
async function jpost(u,b){return (await fetch(u,{method:'POST',body:b})).json();}

async function load(){
  cfg=await jget('/api/config');
  $('log_file').value=cfg.log_file||''; $('default_guy').value=cfg.default_guy||'';
  $('stop_heal_log').value=cfg.stop_heal_log||''; $('ch_binding').value=cfg.ch_binding||'';
  $('ch_threshold').value=cfg.ch_threshold; $('heal_binding').value=cfg.heal_binding||'';
  $('heal_threshold').value=cfg.heal_threshold; $('heal_duck_check_time').value=cfg.heal_duck_check_time;
  $('verbose').checked=!!cfg.verbose;
  $('match_words').value=(cfg.match_words||[]).join('\n');
  $('word_bindings').value=Object.entries(cfg.word_bindings||{}).map(([k,v])=>k+' = '+v).join('\n');
  $('boxes').textContent=JSON.stringify(cfg.bounding_boxes||{},null,2);
}
async function save(){
  cfg.log_file=$('log_file').value; cfg.default_guy=$('default_guy').value;
  cfg.stop_heal_log=$('stop_heal_log').value; cfg.ch_binding=$('ch_binding').value;
  cfg.ch_threshold=parseFloat($('ch_threshold').value)||0; cfg.heal_binding=$('heal_binding').value;
  cfg.heal_threshold=parseFloat($('heal_threshold').value)||0;
  cfg.heal_duck_check_time=parseFloat($('heal_duck_check_time').value)||0; cfg.verbose=$('verbose').checked;
  cfg.match_words=$('match_words').value.split('\n').map(s=>s.trim()).filter(Boolean);
  let wb={}; $('word_bindings').value.split('\n').forEach(l=>{let i=l.indexOf('=');if(i>0)wb[l.slice(0,i).trim()]=l.slice(i+1).trim();}); cfg.word_bindings=wb;
  const r=await jpost('/api/config',JSON.stringify(cfg));
  msg(r.ok?'Saved. (Stop then Start to apply to a running session.)':'Error: '+r.error,!r.ok);
}
async function api(a){await jpost('/api/'+a); refreshStatus();}
async function refreshStatus(){
  const s=await jget('/api/status'); const el=$('status');
  if(!s.running){el.textContent='stopped';el.className='pill';}
  else if(s.paused){el.textContent='paused';el.className='pill pause';}
  else{el.textContent='running';el.className='pill on';}
}
async function refreshHp(){
  try{const r=await jget('/api/read');
    $('hpname').textContent=r.name||'-';
    $('hpval').textContent=(r.pct!=null?r.pct.toFixed(0)+'%':'-');
    const p=Math.max(0,Math.min(100,r.pct||0)), bar=$('hpbar');
    bar.style.width=p+'%';
    bar.style.background=p>60?'var(--good)':p>30?'var(--warn)':'var(--bad)';
  }catch(e){}
}
function cls(line){
  if(/error|cannot|could not|fail/i.test(line))return'err';
  if(/heal|started|resumed|saved|watching/i.test(line))return'heal';
  if(/duck|pause|stopped|skip/i.test(line))return'warn';
  return'';
}
async function refreshLog(){
  const r=await jget('/api/logs?since='+logSeen); logSeen=r.total;
  if(!r.lines.length)return;
  const box=$('log'), atBottom=box.scrollTop+box.clientHeight>=box.scrollHeight-20;
  for(const line of r.lines){const d=document.createElement('div');d.className=cls(line);d.textContent=line;box.appendChild(d);}
  while(box.childElementCount>400)box.removeChild(box.firstChild);
  if(atBottom)box.scrollTop=box.scrollHeight;
}
async function calibrate(){
  const n=$('box_name').value.trim(); if(!n){msg('enter a box name',true);return;}
  msg('A dim overlay will appear - drag a box around the bar (right-click or Esc cancels)...');
  const r=await jpost('/api/calibrate?name='+encodeURIComponent(n));
  if(r.ok){msg('Saved '+r.name+': '+r.width+'x'+r.height+' at ('+r.left+','+r.top+') - reads '+r.pct+'%'); await load();}
  else msg('Calibrate: '+r.error,true);
}
load(); refreshStatus(); refreshHp(); refreshLog();
setInterval(refreshStatus,2000); setInterval(refreshHp,1200); setInterval(refreshLog,1000);
</script>
</div></body></html>"##;
