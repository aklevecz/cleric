//! cleric-rs — native port of the cleric EQ healer bot.
//!
//! A single self-contained executable: screen-region HP-bar reading + log-driven
//! input, no Python/pip/venv. Reads the same config.json as the Python version.

mod calibrate;
mod capture;
mod config;
mod input;
mod watch;
mod web;

use std::mem::zeroed;
use std::ptr::null_mut;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use windows_sys::Win32::UI::HiDpi::{SetProcessDpiAwareness, PROCESS_PER_MONITOR_DPI_AWARE};
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    RegisterHotKey, UnregisterHotKey, MOD_ALT, MOD_CONTROL, MOD_NOREPEAT,
};
use windows_sys::Win32::UI::WindowsAndMessaging::{GetMessageW, MSG, WM_HOTKEY};

const HK_PAUSE: i32 = 1; // Ctrl+Alt+P
const HK_QUIT: i32 = 2; // Ctrl+Alt+Q
const VK_P: u32 = 0x50;
const VK_Q: u32 = 0x51;

fn main() {
    // Make cursor coords (calibration) and GDI capture agree under display
    // scaling — both then use physical pixels.
    unsafe {
        let _ = SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE);
    }

    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("help");
    let cfg = config::load();

    match cmd {
        // Create/replace a bounding box by pointing at its two corners.
        "calibrate" => {
            let name = args.get(2).cloned().unwrap_or_else(|| cfg.default_guy.clone());
            if name.is_empty() {
                eprintln!("usage: cleric calibrate <guy>");
                std::process::exit(1);
            }
            calibrate::calibrate(&name);
        }

        // Capture a configured health bar and print its red % — for verifying
        // a bounding box.
        "read" => {
            let name = args.get(2).cloned().unwrap_or_else(|| cfg.default_guy.clone());
            let cap = match capture::Capturer::new() {
                Some(c) => c,
                None => {
                    eprintln!("could not acquire screen DC");
                    std::process::exit(1);
                }
            };
            match cfg.bounding_boxes.get(&name) {
                Some(b) => match cap.grab(b.left as i32, b.top as i32, b.width as i32, b.height as i32) {
                    Some(buf) => {
                        let pct = capture::red_percentage(&buf, b.width as i32, b.height as i32);
                        println!("{name}: {pct:.2}% full");
                    }
                    None => eprintln!("capture failed — is the bar visible / not occluded?"),
                },
                None => {
                    eprintln!("no bounding box named '{name}'. Create one with: cleric calibrate {name}");
                    if !cfg.bounding_boxes.is_empty() {
                        let names: Vec<&String> = cfg.bounding_boxes.keys().collect();
                        eprintln!("known boxes: {names:?}");
                    }
                }
            }
        }

        // Start the reactive loops; control with global hotkeys.
        "run" => {
            let stop = Arc::new(AtomicBool::new(false));
            let paused = Arc::new(AtomicBool::new(false));
            println!("cleric-rs running (guy='{}').", cfg.default_guy);
            println!("  Ctrl+Alt+P  pause/resume");
            println!("  Ctrl+Alt+Q  quit");
            let h_health = watch::run_health_loop(cfg.clone(), stop.clone(), paused.clone());
            let h_tail = watch::run_log_tail(cfg.clone(), stop.clone(), paused.clone());

            let cm = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT;
            unsafe {
                if RegisterHotKey(null_mut(), HK_PAUSE, cm, VK_P) == 0 {
                    eprintln!("[warn] could not register Ctrl+Alt+P (another app may own it)");
                }
                if RegisterHotKey(null_mut(), HK_QUIT, cm, VK_Q) == 0 {
                    eprintln!("[warn] could not register Ctrl+Alt+Q — close this window to stop");
                }
            }

            // WM_HOTKEY arrives on this thread's message queue (null hwnd).
            unsafe {
                let mut msg: MSG = zeroed();
                while GetMessageW(&mut msg, null_mut(), 0, 0) > 0 {
                    if msg.message == WM_HOTKEY {
                        match msg.wParam as i32 {
                            HK_PAUSE => {
                                let now = !paused.load(Ordering::Relaxed);
                                paused.store(now, Ordering::Relaxed);
                                println!("[run] {}", if now { "PAUSED" } else { "resumed" });
                            }
                            HK_QUIT => break,
                            _ => {}
                        }
                    }
                }
                UnregisterHotKey(null_mut(), HK_PAUSE);
                UnregisterHotKey(null_mut(), HK_QUIT);
            }

            println!("[run] stopping...");
            stop.store(true, Ordering::Relaxed);
            let _ = h_health.join();
            let _ = h_tail.join();
        }

        // Built-in web UI (no framework — plain std HTTP server).
        "ui" => {
            let port: u16 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(7860);
            if std::env::var_os("CLERIC_NO_BROWSER").is_none() {
                let _ = std::process::Command::new("cmd")
                    .args(["/C", "start", "", &format!("http://127.0.0.1:{port}")])
                    .spawn();
            }
            web::serve(port);
        }

        _ => {
            println!("cleric-rs — native EQ healer bot");
            println!();
            println!("usage:");
            println!("  cleric ui [port]        open the web control panel (default port 7860)");
            println!("  cleric calibrate <guy>  point at a health bar's two corners to save a box");
            println!("  cleric read [guy]       capture a configured HP bar and print its fill %");
            println!("  cleric run              run the loops (Ctrl+Alt+P pause, Ctrl+Alt+Q quit)");
            println!();
            println!("config: {} (or set CLERIC_CONFIG)", config::config_path().display());
        }
    }
}
