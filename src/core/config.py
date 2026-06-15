"""Pure config I/O for cleric — standard library only.

This module is intentionally dependency-free (no numpy/PIL/mss/tkinter). It owns
loading/saving config.json and nothing else, so any tool can read configuration
without importing the heavy vision/UI stack.

Config location is anchored to the repo root (the parent of `src/`), not the
current working directory, so it resolves the same no matter where you launch
from. Override with the CLERIC_CONFIG environment variable if needed.
"""

import json
import os

# <repo root>/src/core/config.py  ->  repo root is three levels up.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.environ.get("CLERIC_CONFIG", os.path.join(_REPO_ROOT, "config.json"))

default_config = {
    "log_file": "",
    "default_guy": "mollo",
    "ch_binding": "",
    "ch_threshold": 90,
    "heal_threshold": 0,
    "heal_duck_check_time": 2,
    "heal_binding": "",
    "bounding_boxes": {"mollo": {"left": 0, "top": 0, "width": 0, "height": 0}},
    "match_words": [],
    "word_bindings": {},
    "stop_heal_log": "has been slain",
    "verbose": False,
}


def save_config(config, filename=CONFIG_FILE):
    """Save the configuration to a JSON file (anchored path by default)."""
    with open(filename, "w") as f:
        json.dump(config, f, indent=4)


def load_config(filename=CONFIG_FILE):
    """Load config.json, creating/migrating it as needed. Always returns a dict
    with every default key present, so callers can index safely."""
    if not os.path.exists(filename):
        cfg = default_config.copy()
        save_config(cfg, filename)
        return cfg

    with open(filename, "r") as f:
        try:
            saved = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e} -- using defaults")
            return default_config.copy()

    changed = False

    # Migrate an old flat layout (bounding boxes as top-level keys) into the
    # nested "bounding_boxes" form.
    if "bounding_boxes" not in saved:
        print("Fixing old config file (migrating bounding boxes)...")
        boxes = {k: v for k, v in saved.items() if isinstance(v, dict) and "left" in v}
        for k in boxes:
            saved.pop(k)
        saved["bounding_boxes"] = boxes
        changed = True

    # Backfill any missing default keys so callers never KeyError.
    for key, value in default_config.items():
        if key not in saved:
            saved[key] = value.copy() if isinstance(value, (dict, list)) else value
            changed = True

    if changed:
        save_config(saved, filename)
    return saved


def strip_quotes(s):
    """Remove leading/trailing quotes from a string."""
    return s.strip("\"'")
