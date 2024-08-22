from pynput.keyboard import Key, Controller
import time
keyboard = Controller()

def duck():
    keyboard.press('x')
    time.sleep(0.2)
    keyboard.release('x')

def cast_ch():
    keyboard.press('1')
    time.sleep(0.2)
    keyboard.release('1')

# while True:
#     time.sleep(0.2)
#     keyboard.press(Key.space)
#     time.sleep(0.2)
#     keyboard.release(Key.space)
