import pyautogui
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import time
from main import preprocess_image, get_box, extract_text_from_image
def capture_screen_region(left, top, width, height):
    """Capture a specific region of the screen."""
    screenshot = pyautogui.screenshot(region=(int(left), int(top), int(width), int(height)))
    return screenshot

# def preprocess_image(image):
#     """Preprocess the image to improve OCR accuracy."""
#     gray = ImageOps.grayscale(image)
#     enhancer = ImageEnhance.Contrast(gray)
#     high_contrast = enhancer.enhance(2.0)
#     return high_contrast

# def extract_text_from_image(image):
#     """Extract text from an image using OCR."""
#     custom_config = r'--oem 3 --psm 6'
#     text = pytesseract.image_to_string(image, config=custom_config)
#     return text.strip()

def main():
    # Define the region to capture (you can adjust these values)
    left, top, width, height = get_box()

    print("Starting continuous screen capture and OCR...")
    print("Press Ctrl+C to stop the program.")

    try:
        while True:
            # Capture the specified region
            screenshot = capture_screen_region(left, top, width, height)

            # Preprocess the image
            preprocessed = preprocess_image(screenshot)
            preprocessed.save("LOOPIMG.png")

            # Extract text from the preprocessed image
            extracted_text = extract_text_from_image(preprocessed)

            # Print the extracted text if it's not empty
            if extracted_text:
                print(f"Extracted text: {extracted_text}")

            # Add a small delay to control the capture rate
            time.sleep(0.1)  # Adjust this value to change the capture frequency

    except KeyboardInterrupt:
        print("\nProgram stopped by user.")

if __name__ == "__main__":
    main()