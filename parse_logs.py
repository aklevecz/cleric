import time
import os
import threading
import keyboard
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from press import cast_ch, duck, sit
from red_percentage import get_percentage_of_guy, load_config

stop_event = threading.Event()
observer = None
tail_thread = None

def cast_or_duck_ch(guy_name):
    try:
        print("Casting spell...")
        cast_ch()
        time.sleep(9)
        percentage = get_percentage_of_guy(guy_name)
        print(f"Red progress: {percentage:.2f}%")
        if percentage > 85.0:
            duck()
            time.sleep(1)
            sit()
        else:
            time.sleep(2)
            sit()
    except Exception as e:
        print(f"An error occurred: {e}")

def assist_ma():
    try:
        print("Assisting MA...")
        keyboard.press('e')
        time.sleep(0.2)
        keyboard.release('e')   
    except Exception as e:
        print(f"An error occurred: {e}")

action_map = {
    "go goodegg": cast_or_duck_ch,
    "kill goodegg": assist_ma,
}
class LogFileHandler(FileSystemEventHandler):
    def __init__(self, log_file_path, guy_name, match_words):
        self.log_file_path = log_file_path
        self.guy_name = guy_name
        self.match_words = match_words if isinstance(match_words, list) else [match_words]
        self.file_position = os.path.getsize(log_file_path)  # Start at the end of the file

    def on_modified(self, event):
        if event.src_path == self.log_file_path:
            with open(self.log_file_path, 'r') as file:
                file.seek(self.file_position)
                new_lines = file.readlines()
                self.file_position = file.tell()
                for line in new_lines:
                    print(line, end='')
                    for word in self.match_words:
                        if word in line.lower():
                            if word in action_map:
                                action_map[word](self.guy_name)
                            break
                # for line in new_lines:
                #     print(line, end='')
                #     if any(word in line for word in self.match_words):
                #         cast_or_duck_ch(self.guy_name)

def tail_log_file(log_file_path, guy_name, match_words):
    global observer
    event_handler = LogFileHandler(log_file_path, guy_name, match_words)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(log_file_path), recursive=False)
    observer.start()
    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def start_tail(log_file_path, guy_name, match_words):
    global tail_thread
    stop_event.clear()
    tail_thread = threading.Thread(target=tail_log_file, args=(log_file_path, guy_name, match_words))
    tail_thread.start()
    print("Log file parsing started.")

def stop_tail():
    global observer, tail_thread
    if observer:
        observer.stop()
    stop_event.set()
    if tail_thread:
        tail_thread.join()
    print("Log file parsing stopped.")

# Keybinding functions
def start_tail_keybinding():
    config = load_config()
    log_file_path = config['log_file']
    guy_name = input("Enter the name of the guy you're watching: ")
    start_tail(log_file_path, guy_name, config['match_words'])

def stop_tail_keybinding():
    stop_tail()

if __name__ == "__main__":
    # Set up keybindings
    keyboard.add_hotkey('ctrl+alt+s', start_tail_keybinding)
    keyboard.add_hotkey('ctrl+alt+q', stop_tail_keybinding)

    # Keep the script running to listen for keybindings
    print("Press Ctrl+Alt+S to start tailing the log file.")
    print("Press Ctrl+Alt+Q to stop tailing the log file.")
    print("Press 'esc' to exit the script.")
    keyboard.wait('esc')