import numpy as np
from PIL import Image
import tkinter as tk
from datetime import datetime
import json
import os
import argparse
import pandas as pd
from mss import mss
import time

CONFIG_FILE = 'config.json'

default_config = {
            "log_file": "",
            "default_guy": "mollo",
            "heal_threshold": 0,
            "heal_binding": "",
            "bounding_boxes": {"mollo": {"left": 0, "top": 0, "width": 0, "height": 0}},
            "match_words": [],
            "word_bindings": {},
            "verbose": False
        }
def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config.copy(),
        save_config(default_config.copy())
        return default_config.copy()
    else:
        with open(CONFIG_FILE, 'r') as f:
            try:
                saved_config = json.load(f)
                if 'verbose' not in saved_config:
                    saved_config['verbose'] = False
                    save_config(saved_config)

                # fix old config files
                if 'bounding_boxes' not in saved_config:
                    print("Fixing old config file...")
                    # find all keys that have a bounding box
                    bounding_boxes = {k: v for k, v in saved_config.items() if 'left' in v}
                    saved_config['bounding_boxes'] = bounding_boxes
                    # remove all keys that have a bounding box
                    for k in bounding_boxes.keys():
                        saved_config.pop(k)
                    save_config(saved_config)
                return saved_config
            except json.JSONDecodeError as e:
                print(f"Error parsing config.json: {e}")
                return default_config.copy()
# USES MSS IN FAVOR OF PYAUTOGUI -- BUT SHOULD NOT BE USED FOR SETUP
class ScreenSelector:
    def __init__(self, master):
        self.master = master
        self.start_x = self.start_y = self.end_x = self.end_y = 0
        self.current_x = None
        self.current_y = None
        self.rect = None

        # self.scaling = master.winfo_fpixels('1i') / 72
        self.scaling = 1.0

        master.attributes('-fullscreen', True)
        master.attributes('-alpha', 0.3)
        master.configure(cursor="cross")

        master.bind('<ButtonPress-1>', self.on_button_press)
        master.bind('<B1-Motion>', self.on_move_press)
        master.bind('<ButtonRelease-1>', self.on_button_release)

        self.canvas = tk.Canvas(master, width=master.winfo_screenwidth(), height=master.winfo_screenheight())
        self.canvas.pack()

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_move_press(self, event):
        self.end_x, self.end_y = event.x, event.y
        self.canvas.coords(self.rect, self.start_x, self.start_y, self.end_x, self.end_y)

    def on_button_release(self, event):
        self.end_x = event.x
        self.end_y = event.y
        self.master.quit()

    def get_scaled_coordinates(self):
        left = min(self.start_x, self.end_x) * self.scaling
        top = min(self.start_y, self.end_y) * self.scaling
        right = max(self.start_x, self.end_x) * self.scaling
        bottom = max(self.start_y, self.end_y) * self.scaling
        return map(int, (left, top, right - left, bottom - top))

def save_config(config, filename='config.json'):
    """Save the configuration to a JSON file."""
    script_dir = os.path.dirname(__file__)
    file_path = os.path.join(script_dir, filename)
    file_path = filename
    with open(file_path, 'w') as f:
        json.dump(config, f, indent=4)

# def load_config(filename='config.json'):
#     """Load the configuration from a JSON file."""
#     # script_dir = os.path.dirname(__file__)
#     # file_path = os.path.join(script_dir, filename)
#     file_path = filename
#     if os.path.exists(file_path):
#         with open(file_path, 'r') as f:
#             return json.load(f)
#     return {}

# def save_config(config, filename='config.json'):
#     """Save the configuration to a JSON file."""
#     with open(filename, 'w') as f:
#         json.dump(config, f, indent=4)

# def load_config(filename='config.json'):
#     """Load the configuration from a JSON file."""
#     if os.path.exists(filename):
#         with open(filename, 'r') as f:
#             return json.load(f)
#     return {}

def create_bounding_box():
    """Create a new bounding box and save it to the configuration."""
    name = input("Enter a name for this bounding box: ")
    
    root = tk.Tk()
    app = ScreenSelector(root)
    root.mainloop()
    
    left, top, width, height = app.get_scaled_coordinates()

    config = load_config()
    config['bounding_boxes'][name.strip()] = {'left': left, 'top': top, 'width': width, 'height': height}
    config['default_guy'] = name.strip()
    save_config(config)
    
    print(f"Bounding box '{name}' saved: left={left}, top={top}, width={width}, height={height}")
    
    # Clean up
    root.destroy()
    time.sleep(0.5)  # Short delay to ensure window is closed

def strip_quotes(s):
    """Remove leading and trailing quotes from a string."""
    return s.strip("\"'")

def save_log_file_path(log_file_path=None):
    """Save the log file path to the configuration."""
    if log_file_path is None:
        log_file_path = strip_quotes(input("Enter the path to the log file: "))
    config = load_config()
    config['log_file'] = log_file_path
    save_config(config)
    print(f"Log file path saved: {log_file_path}")

def save_match_word(match_word=None):
    """Save the match word to the configuration."""
    if match_word is None:
        match_word = strip_quotes(input("Enter a word to match in the log file: "))
    config = load_config()
    if 'match_words' not in config:
        config['match_words'] = []
    config['match_words'].append(match_word.strip())
    save_config(config)
    print(f"Match word saved: {match_word}")

def words_to_binding(word=None, binding=None):
    """Save the words to binding mapping to the configuration."""
    if word is None:
        word = strip_quotes(input("Enter a string of word(s) to trigger the binding (e.g. assist me dudes!): "))
    if binding is None:
        binding = strip_quotes(input("Enter the key binding you want triggered (e.g. 6): "))
    config = load_config()
    if 'word_bindings' not in config:
        config['word_bindings'] = {}
    config['word_bindings'][word.strip()] = binding.strip()
    save_config(config)
    print(f"Word binding saved: {word} -> {binding}")

def auto_heal():
    config = load_config()
    heal_threshold = config['heal_threshold'] if 'heal_threshold' in config else 0
    heal_binding = config['heal_binding'] if 'heal_binding' in config else ''

    heal_threshold = int(input(f"Enter the health threshold to auto-heal at (currently {heal_threshold}%): "))
    heal_binding = input(f"Enter the key binding to use for healing (currently {heal_binding}): ")

    config['heal_threshold'] = heal_threshold
    config['heal_binding'] = heal_binding
    save_config(config)
    print(f"Auto-heal settings saved: threshold={heal_threshold}%, binding={heal_binding}")

def main():
    parser = argparse.ArgumentParser(description="Red Progress Bar Analyzer")
    parser.add_argument('--create', action='store_true', help="Create a new bounding box")
    parser.add_argument('--log-file', nargs='?', const='', type=str, help="Specify the log file to use")
    parser.add_argument('--match-word', nargs='?', const='', type=str, help="Specify a word to match in the log file")
    parser.add_argument('--word-binding', nargs='?', const='', type=str, help="Specify a word to match in the log file and the binding on your hotbar")
    parser.add_argument('--auto-heal', action='store_true', help="Automatically heal when health is low")
    args = parser.parse_args()

    if args.create:
        create_bounding_box()
    elif args.log_file is not None:
        save_log_file_path(args.log_file if args.log_file != '' else None)
    elif args.match_word is not None:
        save_match_word(args.match_word if args.match_word != '' else None)
    elif args.word_binding is not None:
        words_to_binding(args.word_binding if args.word_binding != '' else None)
    elif args.auto_heal:
        auto_heal()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()