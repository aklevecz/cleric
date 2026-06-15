//! cleric-rs — native port of the cleric EQ healer bot.
//!
//! A single self-contained executable: screen-region HP-bar reading + log-driven
//! input, no Python/pip/venv. Reads the same config.json as the Python version.

mod capture;
mod config;
mod input;
mod watch;

use std::sync::atomic::AtomicBool;
use std::sync::Arc;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("help");
    let cfg = config::load();

    match cmd {
        // Capture a configured health bar and print its red % — for verifying
        // a bounding box (the Python `red_percentage` debug, on demand).
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
                    eprintln!("no bounding box named '{name}'.");
                    if !cfg.bounding_boxes.is_empty() {
                        let names: Vec<&String> = cfg.bounding_boxes.keys().collect();
                        eprintln!("known boxes: {names:?}");
                    }
                }
            }
        }

        // Start the reactive loops and block until killed (Ctrl+C).
        "run" => {
            let stop = Arc::new(AtomicBool::new(false));
            println!("cleric-rs running (guy='{}'). Ctrl+C to stop.", cfg.default_guy);
            let h_health = watch::run_health_loop(cfg.clone(), stop.clone());
            let h_tail = watch::run_log_tail(cfg.clone(), stop.clone());
            let _ = h_health.join();
            let _ = h_tail.join();
        }

        _ => {
            println!("cleric-rs — native EQ healer bot");
            println!();
            println!("usage:");
            println!("  cleric read [guy]   capture a configured HP bar and print its fill %");
            println!("  cleric run          run the health-check + log-tail loops");
            println!();
            println!("config: {} (or set CLERIC_CONFIG)", config::config_path().display());
        }
    }
}
