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

def press_binding(keysString="shift+x"):
    keys = keysString.split('+')
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