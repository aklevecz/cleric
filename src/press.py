from pynput.keyboard import Key, Controller
import time
keyboard = Controller()

def sit():
    keyboard.press(Key.ctrl)
    keyboard.press('s')
    time.sleep(0.2)
    keyboard.release('s')
    keyboard.release(Key.ctrl)

def duck():
    keyboard.press('x')
    time.sleep(0.2)
    keyboard.release('x')
    keyboard.press('x')
    time.sleep(0.2)
    keyboard.release('x')

def cast_ch():
    keyboard.press('1')
    time.sleep(0.2)
    keyboard.release('1')

def press_binding(key):
    keyboard.press(key)
    time.sleep(0.2)
    keyboard.release(key)

# while True:
#     time.sleep(0.2)
#     keyboard.press(Key.space)
#     time.sleep(0.2)
#     keyboard.release(Key.space)
