import pyautogui
import numpy as np
from PIL import Image
import tkinter as tk
from datetime import datetime, timedelta
import json
import os
import argparse
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, HourLocator
import matplotlib.dates as mdates

import pandas as pd
class ScreenSelector:
    def __init__(self, master):
        self.master = master
        self.start_x = None
        self.start_y = None
        self.current_x = None
        self.current_y = None
        self.rect = None

        root.attributes('-fullscreen', True)
        root.attributes('-alpha', 0.3)
        root.configure(cursor="cross")

        root.bind('<ButtonPress-1>', self.on_button_press)
        root.bind('<B1-Motion>', self.on_move_press)
        root.bind('<ButtonRelease-1>', self.on_button_release)

        self.canvas = tk.Canvas(root, width=root.winfo_screenwidth(), height=root.winfo_screenheight())
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

def capture_screen_region(left, top, width, height):
    """Capture a specific region of the screen."""
    screenshot = pyautogui.screenshot(region=(int(left), int(top), int(width), int(height)))
    return screenshot

def analyze_red_progress(image):
    """Analyze the percentage of red fill based on the rightmost red pixel."""
    img_array = np.array(image)
    
    lower_red = np.array([180, 0, 0])
    upper_red = np.array([255, 50, 50])
    
    red_mask = np.all((img_array >= lower_red) & (img_array <= upper_red), axis=-1)
    
    if not np.any(red_mask):
        print("No red pixels detected in the image.")
        return 0.00
    
    red_columns = np.any(red_mask, axis=0)
    if np.any(red_columns):
        rightmost_red = np.max(np.where(red_columns)[0])
    else:
        return 0.00
    
    total_width = img_array.shape[1] - 1
    percentage = (rightmost_red / total_width) * 100
    
    return round(percentage, 2)

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
    
    global root
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

def append_to_log(name, percentage, timestamp, filename='monitor_log.json'):
    """Append monitoring data to a JSON log file."""
    log_entry = {
        "name": name,
        "percentage": percentage,
        "timestamp": timestamp
    }
    
    if os.path.exists(filename):
        with open(filename, 'r+') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = []
            data.append(log_entry)
            file.seek(0)
            json.dump(data, file, indent=4)
    else:
        with open(filename, 'w') as file:
            json.dump([log_entry], file, indent=4)

def monitor_progress(name):
    """Monitor the progress of a specific bounding box and log the results."""
    config = load_config()
    if name not in config:
        print(f"No bounding box named '{name}' found in the configuration.")
        return
    
    bbox = config[name]
    print(f"Monitoring progress for '{name}'")
    
    while True:
        try:
            screenshot = capture_screen_region(bbox['left'], bbox['top'], bbox['width'], bbox['height'])
            percentage = analyze_red_progress(screenshot)
            timestamp = datetime.now().isoformat()
            print(f"Red progress: {percentage:.2f}%")
            
            # Append to log file
            append_to_log(name, percentage, timestamp)
        except Exception as e:
            print(f"An error occurred: {e}")
        
        pyautogui.sleep(0.1)

def get_percentage_of_guy(name):
    config = load_config()
    if name not in config:
        print(f"No bounding box named '{name}' found in the configuration.")
        return
    
    bbox = config[name]
    print(f"Monitoring progress for '{name}'")
    
    screenshot = capture_screen_region(bbox['left'], bbox['top'], bbox['width'], bbox['height'])
    percentage = analyze_red_progress(screenshot)
    return percentage

def plot_progress(log_file='monitor_log.json'):
    """Plot the progress data from the JSON log file."""
    if not os.path.exists(log_file):
        print(f"Log file '{log_file}' not found.")
        return

    with open(log_file, 'r') as file:
        data = json.load(file)

    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    plt.figure(figsize=(12, 6))
    for name in df['name'].unique():
        name_data = df[df['name'] == name]
        plt.plot(name_data['timestamp'], name_data['percentage'], label=name)

    plt.xlabel('Time')
    plt.ylabel('Percentage')
    plt.title('Health % During Boss')
    plt.legend()
    plt.grid(True)

    plt.ylim(0, 100)  # Set y-axis range from 0 to 100

    plt.gcf().autofmt_xdate()  # Rotate and align the tick labels
    plt.tight_layout()
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="Red Progress Bar Analyzer")
    parser.add_argument('--create', action='store_true', help="Create a new bounding box")
    parser.add_argument('--monitor', type=str, help="Monitor progress for a specific bounding box")
    parser.add_argument('--plot', action='store_true', help="Plot the progress data from the log file")
    args = parser.parse_args()

    if args.create:
        create_bounding_box()
    elif args.monitor:
        monitor_progress(args.monitor)
    elif args.plot:
        plot_progress()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()