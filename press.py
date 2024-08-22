from pynput.keyboard import Key, Controller
import time
keyboard = Controller()

def duck():
    keyboard.press('x')
    time.sleep(0.2)
    keyboard.release('x')

# while True:
#     time.sleep(0.2)
#     keyboard.press(Key.space)
#     time.sleep(0.2)
#     keyboard.release(Key.space)
