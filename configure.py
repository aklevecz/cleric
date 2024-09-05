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

# USES MSS IN FAVOR OF PYAUTOGUI -- BUT SHOULD NOT BE USED FOR SETUP
class ScreenSelector:
    def __init__(self, master):
        self.master = master
        self.start_x = None
        self.start_y = None
        self.current_x = None
        self.current_y = None
        self.rect = None

        master.attributes('-fullscreen', True)
        master.attributes('-alpha', 0.3)
        master.configure(cursor="cross")

        master.bind('<ButtonPress-1>', self.on_button_press)
        master.bind('<B1-Motion>', self.on_move_press)
        master.bind('<ButtonRelease-1>', self.on_button_release)

        self.canvas = tk.Canvas(master, width=master.winfo_screenwidth(), height=master.winfo_screenheight())
        self.canvas.pack()

    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        if not self.rect:
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_move_press(self, event):
        curX = self.canvas.canvasx(event.x)
        curY = self.canvas.canvasy(event.y)

        self.canvas.coords(self.rect, self.start_x, self.start_y, curX, curY)

    def on_button_release(self, event):
        self.current_x = self.canvas.canvasx(event.x)
        self.current_y = self.canvas.canvasy(event.y)
        self.master.quit()




def save_config(config, filename='config.json'):
    """Save the configuration to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(config, f, indent=4)

def load_config(filename='config.json'):
    """Load the configuration from a JSON file."""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def create_bounding_box():
    """Create a new bounding box and save it to the configuration."""
    name = input("Enter a name for this bounding box: ")
    
    root = tk.Tk()
    app = ScreenSelector(root)
    root.mainloop()
    
    left = min(app.start_x, app.current_x)
    top = min(app.start_y, app.current_y)
    width = abs(app.current_x - app.start_x)
    height = abs(app.current_y - app.start_y)
    
    config = load_config()
    config[name] = {'left': left, 'top': top, 'width': width, 'height': height}
    save_config(config)
    
    print(f"Bounding box '{name}' saved: left={left}, top={top}, width={width}, height={height}")
    
    # Clean up
    root.destroy()
    time.sleep(0.5)  # Short delay to ensure window is closed

def save_log_file_path(log_file_path):
    """Save the log file path to the configuration."""
    config = load_config()
    config['log_file'] = log_file_path
    save_config(config)

def save_match_word(match_word):
    """Save the match word to the configuration."""
    config = load_config()
    config['match_words'].append(match_word)
    save_config(config)

def main():
    parser = argparse.ArgumentParser(description="Red Progress Bar Analyzer")
    parser.add_argument('--create', action='store_true', help="Create a new bounding box")
    parser.add_argument('--log-file', type=str, help="Specify the log file to use")
    parser.add_argument('--match-word', type=str, help="Specify a word to match in the log file")
    args = parser.parse_args()

    if args.create:
        create_bounding_box()
    elif args.log_file:
        save_log_file_path(args.log_file)
    elif args.match_word:
        save_match_word(args.match_word)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()