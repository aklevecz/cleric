import pyautogui
import numpy as np
from PIL import Image
import tkinter as tk
from datetime import datetime
from collections import Counter

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

def sample_colors(image, num_colors=10):
    """Sample the most common colors in the image."""
    # Convert image to numpy array
    img_array = np.array(image)
    
    # Reshape the array to 2D (each row is a pixel)
    pixels = img_array.reshape(-1, 3)
    
    # Count the occurrences of each color
    color_counts = Counter(map(tuple, pixels))
    
    # Get the most common colors
    most_common = color_counts.most_common(num_colors)
    
    return most_common

def main():
    global root
    root = tk.Tk()
    app = ScreenSelector(root)
    root.mainloop()

    # Hide the root window before capturing
    root.withdraw()

    # Get the coordinates of the selected region
    left = min(app.start_x, app.current_x)
    top = min(app.start_y, app.current_y)
    width = abs(app.current_x - app.start_x)
    height = abs(app.current_y - app.start_y)
    
    print(f"Selected region: left={left}, top={top}, width={width}, height={height}")
    
    # Capture the specified region
    screenshot = capture_screen_region(left, top, width, height)
    
    # Sample colors
    common_colors = sample_colors(screenshot)
    
    # Print the results
    print("\nMost common colors in the selected region:")
    for color, count in common_colors:
        r, g, b = color
        percentage = (count / (width * height)) * 100
        print(f"RGB: {r}, {g}, {b} - Percentage: {percentage:.2f}%")
    
    # Save the screenshot
    save_path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    screenshot.save(save_path)
    print(f"\nScreenshot saved as: {save_path}")

if __name__ == "__main__":
    main()