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

const INDEX_HTML: &str = r#"<!doctype html>
<html><head><meta charset="utf-8"><title>cleric-rs</title>
<style>
 body{font-family:system-ui,Segoe UI,Arial;max-width:760px;margin:24px auto;padding:0 16px;color:#222}
 h1{font-size:20px} h2{font-size:15px;margin-top:24px;border-bottom:1px solid #ddd;padding-bottom:4px}
 label{display:block;margin:8px 0 2px;font-size:13px;color:#555}
 input[type=text],input[type=number],textarea{width:100%;padding:6px;box-sizing:border-box;font-family:inherit}
 textarea{height:80px} .row{display:flex;gap:12px} .row>div{flex:1}
 button{padding:8px 14px;margin:4px 6px 4px 0;cursor:pointer}
 #status{font-weight:bold} .pill{padding:2px 8px;border-radius:10px;font-size:12px}
 .on{background:#d4f5d0} .off{background:#eee} .pause{background:#ffe9b0}
 #msg{margin:8px 0;color:#0a6;min-height:18px} .err{color:#c00!important}
 pre{background:#f6f6f6;padding:8px;overflow:auto;font-size:12px}
</style></head><body>
<h1>cleric-rs control</h1>

<h2>Run</h2>
<div>status: <span id="status" class="pill off">stopped</span></div>
<button onclick="api('start')">Start</button>
<button onclick="api('stop')">Stop</button>
<button onclick="api('pause')">Pause / Resume</button>
<button onclick="readBar()">Read default bar %</button>
<div id="msg"></div>

<h2>Settings</h2>
<label>Log file path</label><input type="text" id="log_file">
<div class="row">
 <div><label>Default guy</label><input type="text" id="default_guy"></div>
 <div><label>Stop-heal log phrase</label><input type="text" id="stop_heal_log"></div>
</div>
<div class="row">
 <div><label>CH binding</label><input type="text" id="ch_binding"></div>
 <div><label>CH threshold %</label><input type="number" id="ch_threshold"></div>
</div>
<div class="row">
 <div><label>Heal binding</label><input type="text" id="heal_binding"></div>
 <div><label>Heal threshold %</label><input type="number" id="heal_threshold"></div>
 <div><label>Duck-check secs</label><input type="number" step="0.1" id="heal_duck_check_time"></div>
</div>
<label><input type="checkbox" id="verbose"> verbose (echo log lines)</label>
<label>Match words (one per line; a line containing "go" triggers Complete Heal)</label>
<textarea id="match_words"></textarea>
<label>Word bindings (one per line: <code>phrase = key</code>, e.g. <code>assist me = shift+x</code>)</label>
<textarea id="word_bindings"></textarea>
<button onclick="save()">Save settings</button>

<h2>Bounding boxes</h2>
<pre id="boxes"></pre>
<label>Calibrate a box (a dim overlay appears — drag a rectangle over the bar)</label>
<div class="row">
 <div><input type="text" id="box_name" placeholder="name e.g. tank"></div>
 <div><button onclick="calibrate()">Calibrate</button></div>
</div>

<script>
let cfg = {};
function msg(t, err){const m=document.getElementById('msg');m.textContent=t;m.className=err?'err':'';}
async function load(){
  cfg = await (await fetch('/api/config')).json();
  log_file.value=cfg.log_file||''; default_guy.value=cfg.default_guy||'';
  stop_heal_log.value=cfg.stop_heal_log||''; ch_binding.value=cfg.ch_binding||'';
  ch_threshold.value=cfg.ch_threshold; heal_binding.value=cfg.heal_binding||'';
  heal_threshold.value=cfg.heal_threshold; heal_duck_check_time.value=cfg.heal_duck_check_time;
  verbose.checked=!!cfg.verbose;
  match_words.value=(cfg.match_words||[]).join('\n');
  word_bindings.value=Object.entries(cfg.word_bindings||{}).map(([k,v])=>k+' = '+v).join('\n');
  boxes.textContent=JSON.stringify(cfg.bounding_boxes||{},null,2);
}
async function save(){
  cfg.log_file=log_file.value; cfg.default_guy=default_guy.value;
  cfg.stop_heal_log=stop_heal_log.value; cfg.ch_binding=ch_binding.value;
  cfg.ch_threshold=parseFloat(ch_threshold.value)||0; cfg.heal_binding=heal_binding.value;
  cfg.heal_threshold=parseFloat(heal_threshold.value)||0;
  cfg.heal_duck_check_time=parseFloat(heal_duck_check_time.value)||0; cfg.verbose=verbose.checked;
  cfg.match_words=match_words.value.split('\n').map(s=>s.trim()).filter(Boolean);
  let wb={}; word_bindings.value.split('\n').forEach(l=>{let i=l.indexOf('=');if(i>0){wb[l.slice(0,i).trim()]=l.slice(i+1).trim();}}); cfg.word_bindings=wb;
  const r=await (await fetch('/api/config',{method:'POST',body:JSON.stringify(cfg)})).json();
  msg(r.ok?'saved.':'error: '+r.error, !r.ok);
}
async function api(a){const r=await (await fetch('/api/'+a,{method:'POST'})).json(); msg(a+' ok'); refresh();}
async function refresh(){
  const s=await (await fetch('/api/status')).json();
  const el=document.getElementById('status');
  if(!s.running){el.textContent='stopped';el.className='pill off';}
  else if(s.paused){el.textContent='paused';el.className='pill pause';}
  else {el.textContent='running';el.className='pill on';}
}
async function readBar(){const r=await (await fetch('/api/read')).json(); msg(r.name+': '+r.pct+'% full');}
async function calibrate(){
  const n=box_name.value.trim(); if(!n){msg('enter a box name',true);return;}
  msg('A dim overlay will appear — drag a box around the bar (right-click or Esc cancels)…');
  const r=await (await fetch('/api/calibrate?name='+encodeURIComponent(n),{method:'POST'})).json();
  if(r.ok){msg('saved '+r.name+': '+r.left+','+r.top+' '+r.width+'x'+r.height); await load();}
  else msg('error: '+r.error,true);
}
load(); refresh(); setInterval(refresh,2000);
</script>
</body></html>"#;
