# cleric — architecture & how it works

A Python automation bot for an EverQuest-style MMO that **heals a target by
watching its on-screen health bar with computer vision** and **reacts to the
game's text log**. Unlike the sibling project `../eq-bot` (stdlib-only dual-box
hotkey router), this one is a full install-based app: it screenshots HP bars,
measures their fill with NumPy, tails the log with `watchdog`, sends input with
`pynput`, and is driven from a Gradio web UI.

> Naming note: the code is deliberately genericized — `guy` = a character/raid
> member, `LemonQuest`/`lunchpods.exe` in example configs stand in for the real
> game. "CH" = Complete Heal; "duck" = tap crouch to **cancel** an in-progress
> cast. This is group/raid-healing oriented (CH chaining), whereas `eq-bot` is
> solo dual-box.

## The big idea

EQ health bars are a red fill that recedes right→left as HP drops. So you can
read someone's HP% **without any game memory access**: screenshot the bar's
rectangle, find the red pixels, and the **rightmost red column ÷ width = HP%**.
The bot uses that number to decide when to cast Complete Heal or a fast heal,
and tails the log to fire spells/abilities when certain phrases appear.

## Data flow

```
                 config.json  (the single source of truth)
                      │
      ┌───────────────┼────────────────────────┐
      │               │                         │
  ui.py (Gradio)   parse_logs.py            red_percentage.py
  web front-end    REACTIVE engine          VISION layer
  edits config     - watchdog tails log     - mss screenshots a bbox
  start/stop       - word→key triggers      - numpy finds red fill
  threads          - periodic HP check  ───►- returns HP %  ◄── used by parse_logs
      │               │  └─ presses keys via …            │
      └───────────────┴──────────────┬─────────────────────┘
                                      │
                                  press.py  (pynput keyboard/mouse output)
                                  configure.py  (config CRUD + draw-a-box tool)
```

## Modularity & dependency tiers

The project is split so each tool installs and runs independently:

- **`boot/`** is fully standalone — depends only on `pynput`, imports nothing
  from `cleric`. A friend can copy just that folder and use the login automation
  (`pip install -r boot/requirements.txt`). See `boot/README.md`.
- **`src/core/config.py`** is the dependency-free shared core (stdlib only): all
  config I/O lives here, so any tool can read config without pulling in
  numpy/gradio/tkinter. `configure.py` re-exports it for backwards compatibility.
- **`requirements/`** holds per-tool dependency files (`boot.txt`, `vision.txt`,
  `watch.txt`, `web.txt`); root `requirements.txt` just aggregates `web.txt`
  (the full app). `requirements-lock.txt` keeps the exact old pinned freeze for
  reproducibility. Install only what a given tool needs instead of the whole
  stack.

Dependency tiers:

| Tool | Needs |
|------|-------|
| `boot/boot.py` (login) | `pynput` |
| `src/core/config.py` | stdlib only |
| `src/red_percentage.py` (vision) | `numpy`, `Pillow`, `mss` |
| `src/parse_logs.py` + `src/press.py` (watch/input) | `watchdog`, `keyboard`, `pynput` (+ vision) |
| `src/ui.py` (web) | `gradio` (+ all of the above) |

## Files

### `config.json` — central config (managed by `core.config`)
Keys:
- `bounding_boxes` — named screen rectangles around each watched health bar:
  `{ "guy_name": {left, top, width, height} }`. **Absolute desktop coordinates**,
  so they break if the bar moves or display scaling changes.
- `log_file` — full path to the game's text log file.
- `default_guy` — which bounding box (whose HP) is currently being monitored.
- `match_words` — legacy CH trigger list; a line containing one whose text
  includes `"go"` triggers a Complete Heal (see parse_logs).
- `word_bindings` — the generic feature: `{ "log substring": "key binding" }`.
  When a log line contains the substring, the bound key(s) are pressed. Bindings
  support combos (`shift+x`), sequences (`a+b;c`), and a tiny mouse DSL
  (`mouse.scroll(0,-10000)`, `mouse.click()`).
- `ch_threshold` / `heal_threshold` — HP% cutoffs (above ch_threshold after a CH
  → duck to cancel the now-unneeded heal; below heal_threshold → auto-heal).
- `ch_binding` / `heal_binding` — keys for those casts.
- `heal_duck_check_time` — seconds to wait mid-cast before re-checking HP, to
  cancel (duck) if someone else's heal already landed.
- `stop_heal_log` — a log phrase that stops the health-check loop (e.g. a death
  message like "guy has been slain").
- `verbose` — echo every log line into the UI log output.

### `src/core/config.py` — the dependency-free config core
- `load_config`/`save_config`/`default_config`/`strip_quotes`, plus `CONFIG_FILE`
  anchored to the **repo root** (parent of `src/`), overridable via the
  `CLERIC_CONFIG` env var. Fixes the old bug where config resolved relative to
  the current working directory. `load_config` migrates old config shapes and
  **backfills every default key** so callers never `KeyError`.

### `src/red_percentage.py` — the VISION layer
- `capture_screen_region_with_retry(left,top,w,h)` — grabs the bbox with `mss`
  (fast screen capture), retries up to 3× if the frame comes back all-black
  (can happen with hardware-accelerated windows).
- `analyze_red_progress(image)` — the core measurement. Red mask is
  `r>100 AND r>1.5·g AND r>1.5·b`; finds the **rightmost column** containing any
  red, divides by total width → HP percentage. Debug PNGs
  (`detected_red_areas.png`, `red_progress.png`, `no_red_pixels.png`) are now
  written **only when `CLERIC_DEBUG=1`** — previously they were written on every
  frame, i.e. ~once/second from the health loop (constant disk I/O).
- `get_percentage_of_guy(name)` — one-shot: load bbox from config, capture,
  analyze, return %. This is what the heal logic calls.

### `src/parse_logs.py` — the REACTIVE engine (the brain)
- `LogFileHandler` (a `watchdog` `FileSystemEventHandler`): on every log-file
  modification, seeks to the last read position, reads new lines, and per line:
  1. **word_bindings** — if a trigger substring matches, sleep a random 0–2s
     (human-like) and press the bound key. First match wins.
  2. **legacy CH** — if a `match_word` containing `"go"` appears, run
     `cast_or_duck_ch`: cast CH, wait ~9.5s (cast time), read the target's HP;
     if it's already topped off (> ch_threshold) **duck to cancel/finish** then
     sit, else sit. (CH-chain etiquette so you don't waste a heal.)
  3. **stop_heal_log** — if matched, stop the health-check loop.
  - `afk_check()` — presses `k` every 10 minutes to avoid being logged out AFK.
  - The ~9.5s Complete Heal no longer blocks this callback: it's handed to
    `enqueue_action`, which runs it on a single background worker
    (`_action_worker`) so the tailer keeps reading lines during a cast and
    casts can't overlap (duplicate triggers while one is queued are dropped).
- `periodic_health_check` (separate thread): every ~1s reads the monitored
  guy's HP via `get_percentage_of_guy`; if below `heal_threshold`, presses
  `heal_binding`, waits `heal_duck_check_time`, re-checks, and **ducks to cancel**
  if the target was healed in the meantime. HP `0.0` is treated as
  "screenshot failed or target dead → do nothing."
- Threading: `tail_thread` (log watcher) and `health_check_thread` (HP poller)
  run independently, each with its own stop `Event`. `start_*`/`stop_*` manage
  them; `*_keybinding` variants load config first.
- Standalone hotkeys (via `keyboard`, when run directly, not from the UI):
  `Ctrl+Alt+S` start parsing, `Ctrl+Alt+H` start health check, `Ctrl+Alt+Q`
  stop, `Ctrl+Alt+C` change monitored guy, `Shift+Esc` quit.

### `src/press.py` — the ACTUATION layer (output)
- `pynput` keyboard + mouse controllers. `sit()` (Ctrl+S), `duck()` (double-tap
  `x` to cancel a cast), `cast_ch(binding)`, `tag_nearest_enemy()` (q then z).
- `press_binding(keysString)` — parses the binding DSL: `;`-separated steps,
  `+`-separated simultaneous keys, plus `mouse.scroll(x,y)` / `mouse.click()`.
  `key_map` translates names like `space`/`shift`/`f1` to `pynput` `Key` enums.

### `src/configure.py` — the bounding-box drawing GUI + config CLI
- Pure config I/O now lives in `core.config`; this module re-exports it (so
  `from configure import load_config` still works) and keeps the interactive
  bits. It no longer imports numpy/PIL/mss/pandas (those were unused).
- `ScreenSelector` (tkinter): a fullscreen translucent overlay where you
  **click-drag a rectangle** around a health bar; the rect becomes a bounding
  box. This is how you "select an HP bar" in this project — draw a box, not pick
  a pixel. Saved by `create_bounding_box(name)`.
- CLI (`python src/configure.py --create | --log-file | --match-word |
  --word-binding | --auto-heal`) — the batch files just wrap these.

### `src/ui.py` — the Gradio web front-end (recommended entry point)
- Serves a local web UI at `http://127.0.0.1:7860` (`--host 0.0.0.0` to expose
  on LAN). Tabs: General Settings, Auto Heal Settings, Bounding Box Settings
  (add box / edit boxes as JSON), Word Settings (match words + word bindings),
  Log Output (live tail, refreshed every 1s).
- Buttons start/stop log parsing and the health check by calling into
  `parse_logs`. "Save Configuration" writes `config.json`. The Python process in
  the terminal does the work; the browser is just the control panel.

### `boot/boot.py` — login automation (fully standalone)
- Records a macro: launch a program, then your mouse clicks + Enter presses with
  per-step delays (saved to `boot/boot_config.json`, next to the script);
  `--run` replays it to auto-open and log into the game. Driven by `eq-boot.bat`
  / `configure-eq-boot.bat`, or `boot/record-boot.bat` / `boot/run-boot.bat`.
- **Depends only on `pynput`** and imports nothing from `cleric` — copy the
  `boot/` folder anywhere and it works. (Was `src/open-eq.py`.)

### Batch wrappers
`install.bat` (venv + `pip install -r requirements.txt`), `update.bat` (git pull
+ deps), `ui.bat` (launch UI), `start.bat` (run parse_logs with hotkeys),
`configure-*.bat` (wrap configure.py CLI), `eq-boot.bat`/`ui-open-host.bat`.

### `deprecated/` and `archive/`
Old iterations (earlier `ui copy*.py`, `red_percentage copy*.py`, `loop.py`,
`color_sampler.py`, old log parsers) and dated JSON snapshots — not wired into
the current app; ignore unless digging through history.

## Key techniques & gotchas
- **HP read = rightmost-red-column ÷ width.** Robust to partial occlusion of the
  *left* of the bar but assumes a left-anchored red fill on a darker background.
- **Duck-to-cancel.** Casting then ducking when the target is already healthy is
  the core CH-chaining behavior — avoids wasting a 10s Complete Heal.
- **Absolute screen coordinates.** Both bounding boxes (here) and any pixel
  reads are full-desktop coords; re-draw boxes after moving windows / changing
  resolution or DPI. Bars must be **visible/unoccluded** to be captured.
- **Black-frame retries** exist because hardware-accelerated game windows
  sometimes screenshot as black.
- **Heavy dependency stack** (gradio, fastapi/uvicorn, numpy, pandas,
  matplotlib, mss, pynput, keyboard, watchdog, pydub) installed into `venv/` —
  the opposite design choice from `eq-bot`'s stdlib-only constraint.

## Relationship to `../eq-bot`
`eq-bot` is the lightweight, no-install successor for **solo dual-boxing**: a
`ctypes`-only hotkey router. Its newer reactive **pixel watcher** is a stripped
down version of this project's vision layer — `eq-bot` samples a *single* pixel
with `gdi32.GetPixel`, whereas `cleric` screenshots a *whole bounding box* and
measures the red fill with NumPy (more robust, but needs the big dependency
stack). If `eq-bot`'s single-pixel watchers prove too fragile, the
bounding-box + rightmost-red-column method here is the proven upgrade path.
