from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
# from pynput import mouse as m
import tkinter as tk
import time
keyboard = KeyboardController()
mouse = MouseController()

# with m.Events() as events:
#     for event in events:
#         print(event)

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

def cast_ch(binding="1"):
    keyboard.press(binding)
    time.sleep(0.2)
    keyboard.release(binding)

def get_screen_info():
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.withdraw()  # Hide the tkinter window

    center_x = screen_width // 2
    center_y = screen_height // 2

    return {
        "width": screen_width,
        "height": screen_height,
        "center_x": center_x,
        "center_y": center_y
    }

screen_dim = get_screen_info()
def center_mouse():
    mouse.position = (screen_dim["center_x"], screen_dim["center_y"])

def press_binding(keysString="shift+x"):
    split_keys = keysString.split(';')
    if split_keys[-1] == '':
        split_keys.pop()
    for keysString in split_keys:
        # mouse
        if "mouse" in keysString:
            # move mouse to the center of the screen
            center_mouse()
            if "scroll" in keysString:
                # keyString would be mouse.scroll(0, 1)
                x, y = keysString.split('(')[1].split(')')[0].split(',')
                x = int(x.strip())
                y = int(y.strip())
                mouse.scroll(x, y)
                print(f"Scrolling {x}, {y}")
                for _ in range(abs(y)):
                    if y > 0:
                        mouse.scroll(x, 1)
                    else:
                        mouse.scroll(x, -1)
            
            if "mouse.click()" in keysString:
                # keyString would be mouse.press(Button.left)
                print("Clicking mouse")
                mouse.press(Button.left)
                time.sleep(0.2)
                mouse.release(Button.left)
        else:    
            # keyboard
            keys = keysString.split('+')
            print(f"Pressing keys: {keys}")
            for key in keys:
                if key in key_map:
                    key = key_map[key]
                keyboard.press(key)
            time.sleep(0.2)
            for key in keys:
                if key in key_map:
                    key = key_map[key]
                keyboard.release(key)

def tag_nearest_enemy():
    keyboard.press('q')
    time.sleep(0.2)
    keyboard.release('q')
    keyboard.press('z')
    time.sleep(0.2)
    keyboard.release('z')
    
mouse_map = {
    'left': Button.left,
    'right': Button.right,
}

key_map = {
    'space': Key.space,
    'ctrl': Key.ctrl,
    'shift': Key.shift,
    'alt': Key.alt,
    'esc': Key.esc,
    'alt_l': Key.alt_l,
    'alt_r': Key.alt_r,
    'alt_gr': Key.alt_gr,
    'backspace': Key.backspace,
    'caps_lock': Key.caps_lock,
    'cmd': Key.cmd,
    'cmd_l': Key.cmd_l,
    'cmd_r': Key.cmd_r,
    'ctrl_l': Key.ctrl_l,
    'ctrl_r': Key.ctrl_r,
    'delete': Key.delete,
    'down': Key.down,
    'end': Key.end,
    'enter': Key.enter,
    'f1': Key.f1,
    'f2': Key.f2,
    'f3': Key.f3,
    'f4': Key.f4,
    'f5': Key.f5,
    'f6': Key.f6,
    'f7': Key.f7,
    'f8': Key.f8,
    'f9': Key.f9,
    'f10': Key.f10,
    'f11': Key.f11,
    'f12': Key.f12,
    'f13': Key.f13,
    'f14': Key.f14,
    'f15': Key.f15,
    'f16': Key.f16,
    'f17': Key.f17,
    'f18': Key.f18,
    'f19': Key.f19,
    'f20': Key.f20,
    'home': Key.home,
    'left': Key.left,
    'page_down': Key.page_down,
    'page_up': Key.page_up,
    'right': Key.right,
    'shift_l': Key.shift_l,
    'shift_r': Key.shift_r,
    'tab': Key.tab,
    'up': Key.up,
    'media_play_pause': Key.media_play_pause,
    'media_volume_mute': Key.media_volume_mute,
    'media_volume_down': Key.media_volume_down,
    'media_volume_up': Key.media_volume_up,
    'media_previous': Key.media_previous,
    'media_next': Key.media_next,
    'insert': Key.insert,
    'menu': Key.menu,
    'num_lock': Key.num_lock,
    'pause': Key.pause,
    'print_screen': Key.print_screen,
    'scroll_lock': Key.scroll_lock
}