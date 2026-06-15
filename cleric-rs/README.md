# cleric-rs

A native Rust port of the cleric EQ healer bot. Compiles to **one small
self-contained `.exe`** — no Python, no pip, no venv, no Visual C++
redistributable. Your friend copies one file and runs it.

It reads the **same `config.json`** as the Python version (bounding boxes,
thresholds, bindings, log file, word bindings), so configs are interchangeable.

## Why this exists

The Python version's pain was dependencies + setup. This removes them entirely:
the only third-party crates (`windows-sys`, `serde`) are compiled *into* the
binary, so there is nothing to install at runtime. Screen capture and input use
the Win32 API directly via `windows-sys` — no `mss`, `numpy`, `pynput`,
`keyboard`, or `gradio`.

## Build

Needs the Rust toolchain (`rustup`, MSVC host) and the VS C++ build tools (for
the linker — already present if you have Visual Studio).

```
cargo build --release
```

Output: `target/release/cleric.exe` (~0.35 MB). Hand that single file to anyone;
they just need a `config.json` next to it (or point `CLERIC_CONFIG` at one).

## Use

`cleric.exe` is a **command-line** tool — double-clicking it with no command
just prints this help and the window closes instantly (that's not a crash). Run
it with a command from a terminal:

```
cleric ui [port]         open the web control panel (default http://127.0.0.1:7860)
cleric calibrate <guy>   drag a box over a health bar to save it (add 'corners' for F8 mode)
cleric read [guy]        capture a configured HP bar and print its fill %
cleric run               run the loops (Ctrl+Alt+P pause, Ctrl+Alt+Q quit)
```

Prefer to double-click? Use the launchers in this folder — they run the command
and keep the window open: **`cleric-ui.bat`**, **`cleric-calibrate.bat`**,
**`cleric-read.bat`**, **`cleric-run.bat`**. They also point `CLERIC_CONFIG` at
the repo's `config.json` (one level up) so the native tool shares the Python
config.

### Web UI

`cleric ui` starts a tiny built-in HTTP server (hand-rolled on `std::net` — no
web framework, no extra crates) and opens your browser at
`http://127.0.0.1:7860`. The panel shows:

- a **live HP readout + bar** for the default guy (polled ~1×/s),
- **Start / Stop / Pause** controls with a status pill,
- a **live activity log** — everything the bot does (heals, duck-cancels, CH
  casts, triggers, errors) streams here, so you never need the terminal,
- all **settings**, and **Calibrate** (drag-a-box overlay) to add/replace boxes.

Set `CLERIC_NO_BROWSER=1` to skip auto-opening the browser. Tick **verbose** to
also stream every HP read and raw matched log line.

- `calibrate` replaces the Python draw-a-box tool — no Python needed. A dim
  fullscreen overlay appears; **drag a rectangle** around the health bar and
  release (right-click or Esc cancels). The box is saved to `config.json`, set
  as the default guy, and read back so you can confirm the fill %.
  - `cleric calibrate <guy> corners` uses the alternative F8 two-corner method
    (point at top-left, tap F8, point at bottom-right, tap F8) — handy if the
    overlay won't show (e.g. a fullscreen-exclusive game).
- `read` is the verify check: it captures the named bounding box (default:
  `default_guy`) and prints the red-fill %.
- `run` starts both reactive loops and runs until you quit:
  - **Ctrl+Alt+P** pauses/resumes (stops acting, keeps reading); **Ctrl+Alt+Q** quits.
  - **health loop** — polls the guy's HP bar ~1×/s; if below `heal_threshold`
    it presses `heal_binding`, waits `heal_duck_check_time`, re-checks, and
    ducks to cancel if the target already recovered.
  - **log tail** — polls `log_file` for new lines; fires `word_bindings`
    (substring → key), and the legacy `"go"` `match_words` trigger casts
    Complete Heal on a background worker (so tailing never stalls during the
    ~9.5s cast; duplicate triggers while casting are dropped) then ducks/sits.

## How it maps to the Python project

| Python | Here |
|--------|------|
| `red_percentage.py` (mss + numpy) | `capture.rs` — GDI `BitBlt`/`GetDIBits` + a plain red-scan loop |
| `press.py` (pynput/keyboard) | `input.rs` — `SendInput` with scan codes; same `;`/`+` binding DSL |
| `parse_logs.py` (watchdog) | `watch.rs` — file polling + the two loops + CH worker queue |
| `core/config.py` | `config.rs` — serde, same `config.json` schema |

## Performance & old machines

- Capture grabs **only the bounding-box rectangle** (not the whole screen) and
  reuses the screen device context, so it's cheap to poll faster than 1×/s.
- `BitBlt` is fine for windowed games. A **fullscreen-exclusive** DirectX window
  can return a black frame (same limitation as the Python `mss` path); the fix
  would be the Desktop Duplication API / Windows.Graphics.Capture.
- Native binary = tiny footprint and no runtime, so it runs leaner than the
  Python+gradio app on weak hardware. (Build with Rust ≤1.x targeting older
  Windows if you must support Windows 7/8.)

## Implemented

- Built-in **web UI** (`ui`) — a std-only HTTP server, no framework/crates.
- Bounding-box calibration (`calibrate`) — drag-a-box overlay (native Win32),
  or F8 two-corner mode; no Python needed to set up boxes.
- Global hotkeys for `run` (pause/resume + quit).
- Mouse bindings: `mouse.scroll(x,y)` and `mouse.click()` (cursor centered first,
  scroll capped so a huge value doesn't fire thousands of events).
- DPI-aware, so calibration cursor coords and GDI capture use the same pixels.

This is now full feature parity with the Python project, in one ~0.4 MB exe.

## Not ported (by design)

- Login automation — already standalone in the Python `boot/` folder.
