import pyautogui
import pytesseract
from PIL import Image, ImageGrab, ImageOps, ImageEnhance
import tkinter as tk
from tkinter import messagebox
import os
from datetime import datetime
import numpy as np
import cv2
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

def preprocess_image(image):
    """Preprocess the image with upscaling and contrast enhancement."""
    # Convert to grayscale
    gray_image = image.convert('L')
    
    # Upscale the image
    scale_factor = 3  # Increase this for more upscaling
    width, height = gray_image.size
    upscaled = gray_image.resize((width * scale_factor, height * scale_factor), Image.LANCZOS)
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(upscaled)
    high_contrast = enhancer.enhance(1.0)  # Adjust this value if needed
    
    # Optionally, sharpen the image
    enhancer = ImageEnhance.Sharpness(high_contrast)
    sharpened = enhancer.enhance(1.5)  # Adjust this value if needed
    
    return sharpened
# def preprocess_image(image):
#     """Preprocess the image to improve OCR accuracy."""
#     # Convert PIL Image to numpy array
#     scale_factor = 2.0
#     width, height = image.size
#     new_size = (int(width * scale_factor), int(height * scale_factor))
#     image = image.resize(new_size, Image.Resampling.LANCZOS)   
#     img_array = np.array(image)

#     # Convert to grayscale
#     gray = np.dot(img_array[..., :3], [0.2989, 0.5870, 0.1140])
    
#     # Threshold to get white pixels
#     threshold = 100
#     binary = np.where(gray > threshold, 255, 0).astype(np.uint8)
    
#     # Convert back to PIL Image
#     return Image.fromarray(binary)
# def preprocess_image(image):
#     """Preprocess the image to improve OCR accuracy."""
#     # Convert to grayscale
#     scale_factor = 3.0
#     width, height = image.size
#     new_size = (int(width * scale_factor), int(height * scale_factor))
#     image = image.resize(new_size, Image.Resampling.LANCZOS)

#     gray = ImageOps.grayscale(image)
#     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
#     # Invert the image (white text on dark background works better)
#     inverted = ImageOps.invert(gray)
#     inverted = gray
    
#     # Increase contrast
#     enhancer = ImageEnhance.Contrast(inverted)
#     high_contrast = enhancer.enhance(2.0)
#     high_contrast = gray
    
#     # Binarization (convert to pure black and white)
#     threshold = 200
#     _, thresholded = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    
#     return thresholded
#     binary = high_contrast.point(lambda p: p > threshold and 255)
    
#     return gray

def extract_text_from_image(image):
    """Extract text from an image using OCR."""
    # Configure Tesseract parameters
    # custom_config = r'--oem 3 --psm 6'
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789%'
    text = pytesseract.image_to_string(image, config=custom_config)
    return text

def save_image(image, prefix="ocr_image"):
    """Save the image with a timestamp in the current directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    image.save(filename)
    print(f"Image saved as {filename}")
    return filename


def get_box():
    left=1614.0
    top=738.0
    width=33.0
    height=24.0
    return left, top, width, height    

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
    
    left, top, width, height = get_box()
    print(f"left={left}\ntop={top}\nwidth={width}\nheight={height}")
    # Capture the specified region
    screenshot = capture_screen_region(left, top, width, height)

    # Save the original captured image
    # original_image_path = save_image(screenshot, "original")

    # Preprocess the image
    preprocessed = preprocess_image(screenshot)

    # Save the preprocessed image
    preprocessed_image_path = save_image(preprocessed, "preprocessed")

    # Extract text from the preprocessed image
    extracted_text = extract_text_from_image(preprocessed)

    # Print the extracted text
    print("Extracted text:")
    print(extracted_text)

    # Destroy the root window
    root.destroy()


if __name__ == "__main__":
    main2()