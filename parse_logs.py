import time
import os
import hashlib
import threading
import keyboard
from press import cast_ch, duck, sit
from red_percentage import get_percentage_of_guy

stop_event = threading.Event()

def cast_or_duck_ch(guy_name):
    try:
        print("Casting spell...")
        cast_ch()
        time.sleep(9)
        percentage = get_percentage_of_guy(guy_name)
        print(f"Red progress: {percentage:.2f}%")
        if percentage > 85:
            duck()
            sit()
        else:
            time.sleep(2)
            sit()
    except Exception as e:
        print(f"An error occurred: {e}")

def tail_log_file(log_file_path, guy_name, num_lines=10, match_string="ERROR"):
    processed_lines = set()

    def hash_line(line):
        return hashlib.md5(line.encode()).hexdigest()

    def get_last_lines(file, num_lines):
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        buffer_size = 1024
        data = []
        while len(data) < num_lines and file_size > 0:
            if file_size < buffer_size:
                buffer_size = file_size
            file.seek(file_size - buffer_size)
            data = file.readlines() + data
            file_size -= buffer_size
        return data[-num_lines:]

    with open(log_file_path, 'r') as file:
        while not stop_event.is_set():
            lines = get_last_lines(file, num_lines)
            for line in lines:
                line_hash = hash_line(line)
                if line_hash not in processed_lines:
                    if match_string in line:
                        threading.Thread(target=cast_or_duck_ch, args=(guy_name,)).start()
                        print(line, end='')
                    processed_lines.add(line_hash)
            time.sleep(2)  # Wait for 2 seconds before reading the file again

def start_tail(log_file_path, guy_name, num_lines=10, match_string="GO Goodegg"):
    global tail_thread
    stop_event.clear()
    tail_thread = threading.Thread(target=tail_log_file, args=(log_file_path, guy_name, num_lines, match_string))
    tail_thread.start()

def stop_tail():
    stop_event.set()
    tail_thread.join()

# Keybinding functions
def start_tail_keybinding():
    log_file_path = r"C:\Users\Public\Daybreak Game Company\Installed Games\EverQuest\Logs\eqlog_Badegg_teek.txt"
    guy_name = input("Enter the name of the guy you're watching: ")
    start_tail(log_file_path, guy_name, num_lines=10, match_string="GO Goodegg")

def stop_tail_keybinding():
    stop_tail()

# Set up keybindings
keyboard.add_hotkey('ctrl+alt+s', start_tail_keybinding)
keyboard.add_hotkey('ctrl+alt+q', stop_tail_keybinding)

# Keep the script running to listen for keybindings
print("Press Ctrl+Alt+S to start tailing the log file.")
print("Press Ctrl+Alt+Q to stop tailing the log file.")
keyboard.wait('esc')  # Press 'esc' to exit the script