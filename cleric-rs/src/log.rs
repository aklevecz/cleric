//! Tiny in-memory log buffer shared between the loops and the web UI. Every
//! message is both printed to the console and kept in a ring buffer the browser
//! polls via /api/logs, so you don't have to watch the terminal.

use std::collections::VecDeque;
use std::sync::{Mutex, OnceLock};

const CAP: usize = 500;

struct LogBuf {
    lines: VecDeque<String>,
    total: u64, // total lines ever logged (monotonic; used for incremental polling)
}

static BUF: OnceLock<Mutex<LogBuf>> = OnceLock::new();

fn buf() -> &'static Mutex<LogBuf> {
    BUF.get_or_init(|| Mutex::new(LogBuf { lines: VecDeque::new(), total: 0 }))
}

/// Log a line: print to stdout and append to the shared buffer.
pub fn log(msg: impl Into<String>) {
    let m = msg.into();
    println!("{m}");
    if let Ok(mut b) = buf().lock() {
        b.lines.push_back(m);
        b.total += 1;
        while b.lines.len() > CAP {
            b.lines.pop_front();
        }
    }
}

/// Lines logged after the caller's last seen `since` count, plus the new total.
/// The client passes back the total from the previous poll to get only new lines.
pub fn since(since: u64) -> (u64, Vec<String>) {
    let b = buf().lock().unwrap();
    let total = b.total;
    let first = total - b.lines.len() as u64; // count of the oldest buffered line
    let start = since.saturating_sub(first).min(b.lines.len() as u64) as usize;
    (total, b.lines.iter().skip(start).cloned().collect())
}
