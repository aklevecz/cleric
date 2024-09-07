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
from configure import load_config

def capture_screen_region_with_retry(left, top, width, height, max_retries=3, delay=0.5):
    """Capture a specific region of the screen using mss with retries."""
    with mss() as sct:
        region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
        
        for attempt in range(max_retries):
            try:
                screenshot = sct.grab(region)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                # Check if the image is not entirely black
                if np.mean(np.array(img)) > 0:
                    return img
                else:
                    print(f"Attempt {attempt + 1}: Captured image is black. Retrying...")
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
            
            time.sleep(delay)
        
        print("All attempts failed. Returning the last captured image.")
        return img
    
def analyze_red_progress(image):
    """Analyze the percentage of red fill based on the rightmost red pixel, with lenient red detection."""
    img_array = np.array(image)
    
    # Check if the image is entirely black
    if np.mean(img_array) < 1:  # You might need to adjust this threshold
        print("Warning: Captured image appears to be entirely black.")
        return 0.00
    
    # Split the image into its RGB channels
    r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
    
    # Define a lenient condition for "redness"
    # Red channel should be the highest, and significantly higher than the average of green and blue
    red_mask = (r > g) & (r > b) & (r > ((g + b) / 2 + 20))
    
    if not np.any(red_mask):
        print("No red pixels detected in the image.")
        Image.fromarray(img_array).save("no_red_pixels.png")
        return 0.00
    
    red_columns = np.any(red_mask, axis=0)
    if np.any(red_columns):
        rightmost_red = np.max(np.where(red_columns)[0])
    else:
        return 0.00
    
    total_width = img_array.shape[1] - 1
    percentage = (rightmost_red / total_width) * 100
    
    # Save a visualization of the detected red areas
    red_visualization = np.zeros_like(img_array)
    red_visualization[red_mask] = [255, 0, 0]  # Set detected red pixels to bright red
    Image.fromarray(red_visualization).save("detected_red_areas.png")
    
    Image.fromarray(img_array).save("red_progress.png")
    return round(percentage, 2)

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
            screenshot = capture_screen_region_with_retry(bbox['left'], bbox['top'], bbox['width'], bbox['height'])
            percentage = analyze_red_progress(screenshot)
            timestamp = datetime.now().isoformat()
            print(f"Red progress: {percentage:.2f}%")
            
            # Append to log file
            append_to_log(name, percentage, timestamp)
        except Exception as e:
            print(f"An error occurred: {e}")
        
        time.sleep(0.1)

def get_percentage_of_guy(name):
    config = load_config()
    if name not in config:
        print(f"No bounding box named '{name}' found in the configuration.")
        return
    
    bbox = config[name]
    print(f"Monitoring progress for '{name}'")
    
    screenshot = capture_screen_region_with_retry(bbox['left'], bbox['top'], bbox['width'], bbox['height'])
    percentage = analyze_red_progress(screenshot)
    return percentage

def main():
    parser = argparse.ArgumentParser(description="Red Progress Bar Analyzer")
    parser.add_argument('--monitor', type=str, help="Monitor progress for a specific bounding box")
    args = parser.parse_args()

    if args.monitor:
        monitor_progress(args.monitor)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()