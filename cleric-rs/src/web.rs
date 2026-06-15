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
:root{--bg:#0e1116;--bg2:#11151b;--card:#171b22;--line:#272d37;--fg:#e7ebf1;--muted:#8a94a4;--accent:#5b9dff;--good:#46d17e;--warn:#f3c969;--bad:#ff6b6b}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(180deg,#0c0f14,#0e1116 240px);color:var(--fg);font:14px/1.5 system-ui,Segoe UI,Arial}
.wrap{max-width:880px;margin:0 auto;padding:22px 18px 70px}
header{display:flex;align-items:center;gap:12px;margin-bottom:18px}
.brand{font-size:19px;font-weight:700;letter-spacing:.4px}
.brand .dot{color:var(--accent)}
.pill{padding:4px 11px;border-radius:999px;font-size:12px;font-weight:600;background:#222834;color:var(--muted);border:1px solid var(--line)}
.pill.on{background:rgba(70,209,126,.16);color:var(--good);border-color:rgba(70,209,126,.4)}
.pill.pause{background:rgba(243,201,105,.16);color:var(--warn);border-color:rgba(243,201,105,.4)}
.spacer{flex:1}
.controls{display:flex;gap:8px;flex-wrap:wrap}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px;box-shadow:0 1px 0 rgba(255,255,255,.02) inset}
.card>h2{font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);margin:0 0 14px;font-weight:700}
.sub{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:700;margin:18px 0 8px}
button{font:inherit;font-weight:600;padding:9px 15px;border-radius:9px;border:1px solid var(--line);background:#222a35;color:var(--fg);cursor:pointer;transition:.12s}
button:hover{border-color:#3c4757;background:#28313e} button:active{transform:translateY(1px)}
button.primary{background:var(--accent);border-color:var(--accent);color:#05101f}
button.primary:hover{background:#74adff}
button.danger{color:var(--bad);border-color:transparent;background:transparent}
button.danger:hover{background:rgba(255,107,107,.12)}
.btn-sm{padding:5px 10px;font-size:12px;border-radius:7px}
.val{font-size:34px;font-weight:800;line-height:1;font-variant-numeric:tabular-nums}
.muted{color:var(--muted)}
.bar{height:14px;background:#0a0d12;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-top:12px}
.bar>i{display:block;height:100%;width:0;background:var(--good);transition:width .4s,background .4s}
label{display:block;margin:0 0 5px;font-size:12px;color:var(--muted)}
input,textarea{width:100%;padding:9px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg2);color:var(--fg);font:inherit;transition:.12s}
input:focus,textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(91,157,255,.18)}
textarea{height:70px;resize:vertical}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.field{display:flex;flex-direction:column}
.chk{display:flex;align-items:center;gap:9px;margin-top:14px;color:var(--muted)} .chk input{width:auto}
.logwrap{border:1px solid var(--line);border-radius:10px;overflow:hidden}
.logbar{display:flex;align-items:center;gap:7px;padding:8px 12px;background:#10141a;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted)}
.logbar .d{width:9px;height:9px;border-radius:50%;background:#3a4250}
#log{background:#0a0d11;height:250px;overflow:auto;padding:10px 12px;font:12px/1.55 ui-monospace,Consolas,monospace;white-space:pre-wrap}
#log div{color:#c2c9d4} #log .heal{color:var(--good)} #log .warn{color:var(--warn)} #log .err{color:var(--bad)}
#log .empty{color:var(--muted)}
#msg{min-height:18px;color:var(--accent);margin-top:12px;font-size:13px} #msg.err{color:var(--bad)}
.boxrow{display:flex;align-items:center;gap:12px;padding:11px 0;border-top:1px solid var(--line)}
.boxrow:first-child{border-top:none}
.boxinfo{flex:1;min-width:0}
.boxname{font-weight:600;display:flex;align-items:center;gap:8px}
.boxdim{color:var(--muted);font-size:12px;margin-top:2px;font-variant-numeric:tabular-nums}
.badge{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--accent);background:rgba(91,157,255,.15);border:1px solid rgba(91,157,255,.4);padding:1px 7px;border-radius:999px}
.boxacts{display:flex;gap:6px;flex-wrap:wrap}
.empty{color:var(--muted);padding:6px 0}
.addrow{display:flex;gap:10px;margin-top:14px}
.addrow input{flex:1}
.wbrow{display:flex;gap:8px;margin-bottom:8px}
.wbrow .wb-k{flex:1.3} .wbrow .wb-v{flex:1}
</style></head><body><div class="wrap">

<header>
 <span class="brand">cleric<span class="dot">.</span></span>
 <span id="status" class="pill">stopped</span>
 <span class="spacer"></span>
 <div class="controls">
  <button class="primary" onclick="api('start')">Start</button>
  <button onclick="api('pause')">Pause</button>
  <button class="danger" onclick="api('stop')">Stop</button>
 </div>
</header>

<div class="card">
 <h2>Status</h2>
 <div class="val" id="hpval">-</div>
 <div class="muted">watching <span id="hpname">-</span></div>
 <div class="bar"><i id="hpbar"></i></div>
 <div id="msg"></div>
</div>

<div class="card">
 <h2>Activity</h2>
 <div class="logwrap"><div class="logbar"><span class="d"></span>live log</div><div id="log"></div></div>
</div>

<div class="card">
 <h2>Health bars</h2>
 <div id="boxes"></div>
 <div class="addrow">
  <input id="box_name" placeholder="new bar name, e.g. tank">
  <button class="primary" onclick="calibrate()">+ Calibrate</button>
 </div>
 <div class="muted" style="font-size:12px;margin-top:8px">A dim overlay appears — drag a rectangle over the red part of the bar.</div>
</div>

<div class="card">
 <h2>Settings</h2>

 <div class="sub">Auto-heal</div>
 <div class="grid">
  <div class="field"><label>Heal binding</label><input id="heal_binding"></div>
  <div class="field"><label>Heal below %</label><input type="number" id="heal_threshold"></div>
  <div class="field"><label>Duck-check secs</label><input type="number" step="0.1" id="heal_duck_check_time"></div>
 </div>

 <div class="sub">Complete Heal (group "go" trigger)</div>
 <div class="grid">
  <div class="field"><label>CH binding</label><input id="ch_binding"></div>
  <div class="field"><label>CH cancel above %</label><input type="number" id="ch_threshold"></div>
 </div>

 <div class="sub">Log</div>
 <div class="field"><label>EQ log file path</label><input id="log_file"></div>
 <div class="field" style="margin-top:10px"><label>Stop-heal phrase (e.g. "has been slain")</label><input id="stop_heal_log"></div>

 <div class="sub">Triggers</div>
 <label>Match words — one per line; a line containing "go" casts Complete Heal</label>
 <textarea id="match_words"></textarea>
 <label style="margin-top:12px">Word bindings — when a log line contains the phrase, press the key</label>
 <div id="wb"></div>
 <button class="btn-sm" onclick="addBindingRow()">+ Add binding</button>

 <label class="chk"><input type="checkbox" id="verbose"> verbose — log every HP read and matched log line</label>
 <div style="margin-top:16px"><button class="primary" onclick="save()">Save settings</button></div>
</div>

<script>
const $=id=>document.getElementById(id);
let cfg={}, logSeen=0;
function msg(t,e){const m=$('msg');m.textContent=t||'';m.className=e?'err':'';}
async function jget(u){return (await fetch(u)).json();}
async function jpost(u,b){return (await fetch(u,{method:'POST',body:b})).json();}
function mkbtn(label,cls,fn){const b=document.createElement('button');b.textContent=label;b.className='btn-sm'+(cls?' '+cls:'');b.onclick=fn;return b;}

async function load(){
  cfg=await jget('/api/config');
  $('log_file').value=cfg.log_file||''; $('stop_heal_log').value=cfg.stop_heal_log||'';
  $('ch_binding').value=cfg.ch_binding||''; $('ch_threshold').value=cfg.ch_threshold;
  $('heal_binding').value=cfg.heal_binding||''; $('heal_threshold').value=cfg.heal_threshold;
  $('heal_duck_check_time').value=cfg.heal_duck_check_time; $('verbose').checked=!!cfg.verbose;
  $('match_words').value=(cfg.match_words||[]).join('\n');
  renderBindings(); renderBoxes();
}
function renderBoxes(){
  const wrap=$('boxes'); wrap.innerHTML='';
  const boxes=cfg.bounding_boxes||{}, names=Object.keys(boxes).sort();
  if(!names.length){const e=document.createElement('div');e.className='empty';e.textContent='No health bars yet — add one below.';wrap.appendChild(e);return;}
  for(const name of names){
    const b=boxes[name], row=document.createElement('div'); row.className='boxrow';
    const info=document.createElement('div'); info.className='boxinfo';
    const nm=document.createElement('div'); nm.className='boxname'; nm.textContent=name;
    if(cfg.default_guy===name){const bd=document.createElement('span');bd.className='badge';bd.textContent='default';nm.appendChild(bd);}
    const dim=document.createElement('div'); dim.className='boxdim';
    dim.textContent=Math.round(b.width)+'×'+Math.round(b.height)+' px at ('+Math.round(b.left)+', '+Math.round(b.top)+')';
    info.appendChild(nm); info.appendChild(dim);
    const acts=document.createElement('div'); acts.className='boxacts';
    if(cfg.default_guy!==name)acts.appendChild(mkbtn('Set default','',()=>setDefault(name)));
    acts.appendChild(mkbtn('Recalibrate','',()=>calibrate(name)));
    acts.appendChild(mkbtn('Delete','danger',()=>{if(confirm('Delete bar "'+name+'"?'))delBox(name);}));
    row.appendChild(info); row.appendChild(acts); wrap.appendChild(row);
  }
}
function renderBindings(){
  const t=$('wb'); t.innerHTML='';
  for(const [k,v] of Object.entries(cfg.word_bindings||{})) addBindingRow(k,v);
}
function addBindingRow(k,v){
  const row=document.createElement('div'); row.className='wbrow';
  const a=document.createElement('input'); a.className='wb-k'; a.placeholder='log phrase'; a.value=k||'';
  const b=document.createElement('input'); b.className='wb-v'; b.placeholder='key e.g. shift+x'; b.value=v||'';
  row.appendChild(a); row.appendChild(b); row.appendChild(mkbtn('×','danger',()=>row.remove()));
  $('wb').appendChild(row);
}
function collectBindings(){
  const wb={}; document.querySelectorAll('#wb .wbrow').forEach(r=>{
    const k=r.querySelector('.wb-k').value.trim(), v=r.querySelector('.wb-v').value.trim();
    if(k&&v)wb[k]=v;
  }); return wb;
}
async function save(){
  cfg.log_file=$('log_file').value; cfg.stop_heal_log=$('stop_heal_log').value;
  cfg.ch_binding=$('ch_binding').value; cfg.ch_threshold=parseFloat($('ch_threshold').value)||0;
  cfg.heal_binding=$('heal_binding').value; cfg.heal_threshold=parseFloat($('heal_threshold').value)||0;
  cfg.heal_duck_check_time=parseFloat($('heal_duck_check_time').value)||0; cfg.verbose=$('verbose').checked;
  cfg.match_words=$('match_words').value.split('\n').map(s=>s.trim()).filter(Boolean);
  cfg.word_bindings=collectBindings();
  const r=await jpost('/api/config',JSON.stringify(cfg));
  msg(r.ok?'Saved. (Stop then Start to apply to a running session.)':'Error: '+r.error,!r.ok);
}
async function mutateConfig(fn){
  const c=await jget('/api/config'); fn(c); await jpost('/api/config',JSON.stringify(c));
  cfg.bounding_boxes=c.bounding_boxes; cfg.default_guy=c.default_guy; renderBoxes();
}
function setDefault(n){mutateConfig(c=>{c.default_guy=n;});}
function delBox(n){mutateConfig(c=>{delete c.bounding_boxes[n]; if(c.default_guy===n)c.default_guy=Object.keys(c.bounding_boxes)[0]||'';});}

async function api(a){await jpost('/api/'+a); refreshStatus();}
async function refreshStatus(){
  const s=await jget('/api/status'), el=$('status');
  if(!s.running){el.textContent='stopped';el.className='pill';}
  else if(s.paused){el.textContent='paused';el.className='pill pause';}
  else{el.textContent='running';el.className='pill on';}
}
async function refreshHp(){
  try{const r=await jget('/api/read');
    $('hpname').textContent=r.name||'-';
    $('hpval').textContent=(r.pct!=null?r.pct.toFixed(0)+'%':'-');
    const p=Math.max(0,Math.min(100,r.pct||0)), bar=$('hpbar');
    bar.style.width=p+'%'; bar.style.background=p>60?'var(--good)':p>30?'var(--warn)':'var(--bad)';
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
async function calibrate(name){
  const n=(typeof name==='string'?name:$('box_name').value.trim());
  if(!n){msg('enter a bar name first',true);return;}
  msg('A dim overlay will appear — drag a box around the bar (right-click or Esc cancels)…');
  const r=await jpost('/api/calibrate?name='+encodeURIComponent(n));
  if(r.ok){msg('Saved "'+r.name+'": '+r.width+'×'+r.height+' — reads '+r.pct+'%'); $('box_name').value=''; await load();}
  else msg('Calibrate: '+r.error,true);
}
load(); refreshStatus(); refreshHp(); refreshLog();
setInterval(refreshStatus,2000); setInterval(refreshHp,1200); setInterval(refreshLog,1000);
</script>
</div></body></html>"##;
