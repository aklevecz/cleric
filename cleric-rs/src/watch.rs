//! The two reactive loops, mirroring the Python bot:
//!  - health loop: poll a guy's HP bar, heal below threshold, duck-cancel if it
//!    recovered while casting.
//!  - log tail: poll the log file for new lines; fire word->key bindings and the
//!    legacy "go" Complete-Heal trigger. The ~9.5s CH cast runs on a separate
//!    worker so tailing never stalls (dropped if a cast is already in flight).

use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::sync_channel;
use std::sync::Arc;
use std::thread::{self, sleep, JoinHandle};
use std::time::Duration;

use crate::capture::{red_percentage, Capturer};
use crate::config::Config;
use crate::input;

/// One HP reading for a configured guy (0.0 if no box / capture failed).
fn pct_for(cap: &Capturer, cfg: &Config, name: &str) -> f32 {
    let Some(b) = cfg.bounding_boxes.get(name) else {
        return 0.0;
    };
    match cap.grab(b.left as i32, b.top as i32, b.width as i32, b.height as i32) {
        Some(buf) => red_percentage(&buf, b.width as i32, b.height as i32),
        None => 0.0,
    }
}

pub fn run_health_loop(cfg: Config, stop: Arc<AtomicBool>) -> JoinHandle<()> {
    thread::spawn(move || {
        let cap = match Capturer::new() {
            Some(c) => c,
            None => {
                eprintln!("[health] could not acquire screen DC");
                return;
            }
        };
        let name = cfg.default_guy.clone();
        if name.is_empty() {
            eprintln!("[health] no default_guy configured");
            return;
        }
        while !stop.load(Ordering::Relaxed) {
            let pct = pct_for(&cap, &cfg, &name);
            if cfg.verbose {
                println!("[health] {name}: {pct:.1}%");
            }
            if pct > 0.0 && pct < cfg.heal_threshold {
                println!("[health] {name} at {pct:.1}% -> heal ({})", cfg.heal_binding);
                input::press_binding(&cfg.heal_binding);
                sleep(Duration::from_secs_f32(cfg.heal_duck_check_time));
                let again = pct_for(&cap, &cfg, &name);
                if again > cfg.heal_threshold {
                    println!("[health] recovered to {again:.1}% -> duck-cancel");
                    input::duck();
                }
            }
            sleep(Duration::from_secs(1));
        }
    })
}

pub fn run_log_tail(cfg: Config, stop: Arc<AtomicBool>) -> JoinHandle<()> {
    thread::spawn(move || {
        // Action worker for the long (~9.5s) CH cast. A rendezvous channel
        // (capacity 0) means try_send fails while the worker is busy casting,
        // so duplicate "go" triggers are dropped instead of piling up.
        let (tx, rx) = sync_channel::<()>(0);
        let cfg_worker = cfg.clone();
        thread::spawn(move || {
            let cap = Capturer::new();
            while rx.recv().is_ok() {
                println!("[ch] casting Complete Heal ({})", cfg_worker.ch_binding);
                input::press_binding(&cfg_worker.ch_binding);
                sleep(Duration::from_secs_f32(9.5));
                if let Some(ref c) = cap {
                    let pct = pct_for(c, &cfg_worker, &cfg_worker.default_guy);
                    if pct > cfg_worker.ch_threshold {
                        println!("[ch] target at {pct:.1}% -> duck-cancel");
                        input::duck();
                    }
                }
                // Resume medding after the cast, like the Python cast_or_duck_ch.
                input::sit();
            }
        });

        let mut file = match File::open(&cfg.log_file) {
            Ok(f) => f,
            Err(e) => {
                eprintln!("[tail] cannot open log '{}': {e}", cfg.log_file);
                return;
            }
        };
        let mut pos = file.seek(SeekFrom::End(0)).unwrap_or(0);
        println!("[tail] watching {}", cfg.log_file);

        let word_bindings: Vec<(String, String)> = cfg
            .word_bindings
            .iter()
            .map(|(k, v)| (k.to_lowercase(), v.clone()))
            .collect();
        let match_words: Vec<String> = cfg.match_words.iter().map(|w| w.to_lowercase()).collect();

        while !stop.load(Ordering::Relaxed) {
            let len = file.metadata().map(|m| m.len()).unwrap_or(pos);
            if len > pos {
                if file.seek(SeekFrom::Start(pos)).is_ok() {
                    let mut bytes = vec![0u8; (len - pos) as usize];
                    if file.read_exact(&mut bytes).is_ok() {
                        pos = len;
                        let text = String::from_utf8_lossy(&bytes);
                        for line in text.lines() {
                            let low = line.to_lowercase();
                            if cfg.verbose {
                                println!("{line}");
                            }
                            for (word, binding) in &word_bindings {
                                if low.contains(word) {
                                    println!("[trigger] '{word}' -> {binding}");
                                    input::press_binding(binding);
                                    break;
                                }
                            }
                            for w in &match_words {
                                if low.contains(w) {
                                    if w.contains("go") {
                                        if tx.try_send(()).is_err() {
                                            println!("[ch] already casting, skipping trigger");
                                        }
                                    }
                                    break;
                                }
                            }
                        }
                    }
                }
            } else if len < pos {
                // log rotated/truncated — restart from the new end
                pos = len;
            }
            sleep(Duration::from_millis(250));
        }
    })
}
