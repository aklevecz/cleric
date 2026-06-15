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

```
cleric read [guy]   capture a configured HP bar and print its fill %  (verify a box)
cleric run          run the health-check + log-tail loops
```

- `read` is the calibration check: it captures the named bounding box (default:
  `default_guy` from config) and prints the red-fill %. Use it to confirm a box
  lines up with a health bar.
- `run` starts both reactive loops and blocks until you Ctrl+C:
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

## Not yet ported (intentionally — first slice)

- The draw-a-box GUI for creating bounding boxes (use the Python
  `configure.py --create`, or hand-edit `config.json`; coords are shared).
- The gradio web UI (config is the shared `config.json`).
- Mouse bindings (`mouse.scroll(...)` / `mouse.click()`) — skipped with a warning.
- Global start/stop hotkeys — `run` uses Ctrl+C for now.
- Login automation — already standalone in the Python `boot/` folder.
