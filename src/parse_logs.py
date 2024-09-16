import time
import os
import threading
import random
import keyboard
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from press import cast_ch, duck, sit, press_binding
from configure import load_config, save_config
from red_percentage import get_percentage_of_guy
from queue import Queue
from collections import deque

stop_event = threading.Event()
observer = None
tail_thread = None
health_check_thread = None
current_guy_name = ""
log_deque = deque(maxlen=1000)  # Store last 1000 log messages

def log_message(message):
    print(message)
    log_deque.append(message)

def get_logs():
    return "\n".join(log_deque)
# Periodic health checking and healing
def check_health_and_heal(guy_name, heal_threshold, heal_binding):
    try:
        log_message(f"Checking health for {guy_name}...")
        percentage = get_percentage_of_guy(guy_name)
        log_message(f"Red progress: {percentage:.2f}%")

        if percentage == 0.0:
            log_message("Screenshot error or guy is dead, do nothing")
            return
        if percentage < heal_threshold:
            press_binding(heal_binding)
    except Exception as e:
        log_message(f"An error occurred: {e}")

def periodic_health_check(guy_name, config):
    while not stop_event.is_set():
        check_health_and_heal(guy_name, config['heal_threshold'], config['heal_binding'])
        # tag_nearest_enemy()
        # random_sleep_interval = random.randint(5, 20) 
        random_sleep_interval = 2
        time.sleep(random_sleep_interval)  # Wait for 2 seconds before the next check

# Periodic health checking and healing end

# Not being used
def cast_or_duck_ch_stand(guy_name):
    try:
        log_message("Casting spell...")
        cast_ch()
        time.sleep(9)
        percentage = get_percentage_of_guy(guy_name)
        log_message(f"Red progress: {percentage:.2f}%")
        if percentage > 85.0:
            duck()
    except Exception as e:
        log_message(f"An error occurred: {e}")

def cast_or_duck_ch(guy_name):
    try:
        log_message("Casting spell...")
        cast_ch()
        time.sleep(9)
        percentage = get_percentage_of_guy(guy_name)
        log_message(f"Red progress: {percentage:.2f}%")
        if percentage > 85.0:
            duck()
            time.sleep(1)
            sit()
        else:
            time.sleep(2)
            sit()
    except Exception as e:
        log_message(f"An error occurred: {e}")

ten_mintues_in_seconds = 60 * 10

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, log_file_path, guy_name, match_words, word_bindings):
        self.log_file_path = log_file_path
        self.guy_name = guy_name
        self.match_words = match_words if isinstance(match_words, list) else [match_words]
        self.word_bindings = word_bindings if isinstance(word_bindings, dict) else {}
        self.file_position = os.path.getsize(log_file_path)  # Start at the end of the file
        self.last_timestamp = time.time()

    def afk_check(self):
        current_timestamp = time.time()
        if current_timestamp - self.last_timestamp > ten_mintues_in_seconds:
            self.last_timestamp = current_timestamp
            press_binding('k')

    def on_modified(self, event):
        if event.src_path == self.log_file_path:
            self.afk_check()
            with open(self.log_file_path, 'r') as file:
                file.seek(self.file_position)
                new_lines = file.readlines()
                self.file_position = file.tell()
                for line in new_lines:
                    # log_message(line)
                    for wordsString in self.word_bindings.keys():
                        if wordsString in line.lower():
                            time.sleep(random.uniform(0, 2))
                            keyBinding = self.word_bindings[wordsString]
                            log_message(f"Pressing key binding: {keyBinding} for trigger words: {wordsString}")
                            press_binding(keyBinding)
                            break

                    for word in self.match_words:
                        if word in line.lower():
                            if "go" in word:
                                cast_or_duck_ch(self.guy_name)
                            # if word in action_map:
                                # action_map[word](self.guy_name)
                            break

def tail_log_file(log_file_path, guy_name, match_words, word_bindings):
    global observer
    event_handler = LogFileHandler(log_file_path, guy_name, match_words, word_bindings)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(log_file_path), recursive=False)
    observer.start()
    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def stop_tail():
    global observer, tail_thread, health_check_thread
    if observer:
        observer.stop()
    stop_event.set()
    if tail_thread:
        tail_thread.join()
    if health_check_thread:
        health_check_thread.join()
    log_message("Log file parsing and/or health check stopped.")

def get_default_guy_name(config):
    for k, v in config.items():
        if isinstance(v, dict):
            if "left" in v:
                return config['default_guy']
                break
    return ""

def start_tail(log_file_path, guy_name, match_words, word_bindings):
    global tail_thread
    if tail_thread:
        log_message("Stopping previous tail thread...")
        stop_tail()
    stop_event.clear()
    current_guy_name = guy_name
    tail_thread = threading.Thread(target=tail_log_file, args=(log_file_path, guy_name, match_words, word_bindings))
    tail_thread.start()
    log_message("Log file parsing started.")
    log_message(f"Now monitoring: {current_guy_name}")
    log_message(f"Match words: {match_words}")
    log_message(f"Word bindings: {word_bindings}")

# Keybinding functions
def start_tail_keybinding():
    config = load_config()
    log_file_path = config['log_file']
    guy_name = get_default_guy_name(config)
    start_tail(log_file_path, guy_name, config['match_words'], config['word_bindings'])

def start_health_check(guy_name, config):
    global health_check_thread
    log_message("Starting health check...")
    if health_check_thread:
        log_message("Stopping previous health check thread...")
        stop_tail()
    stop_event.clear()
    health_check_thread = threading.Thread(target=periodic_health_check, args=(guy_name, config))
    health_check_thread.start()

def start_health_check_keybinding():
    config = load_config()
    guy_name = get_default_guy_name(config)
    start_health_check(guy_name, config)


def stop_tail_keybinding():
    stop_tail()

def change_person_keybinding():
    stop_tail()
    change_monitored_person()

def change_monitored_person():
    global current_guy_name
    new_guy_name = input("Enter the name of the new guy you're watching: ")
    current_guy_name = new_guy_name
    config = load_config()
    config['default_guy'] = new_guy_name
    log_message(f"Default guy changed to: {new_guy_name}")
    save_config(config)
    start_tail(config['log_file'], current_guy_name, config['match_words'], config['word_bindings'])

    log_message(f"Now monitoring: {current_guy_name}")

if __name__ == "__main__":
    # Set up keybindings
    keyboard.add_hotkey('ctrl+alt+s', start_tail_keybinding)
    keyboard.add_hotkey('ctrl+alt+h', start_health_check_keybinding)
    keyboard.add_hotkey('ctrl+alt+q', stop_tail_keybinding)
    keyboard.add_hotkey('ctrl+alt+c', change_person_keybinding)  # New keybinding

    # Keep the script running to listen for keybindings
    print("Press Ctrl+Alt+S to start parsing commands.")
    print("Press Ctrl+Alt+H to start auto heal.")
    print("Press Ctrl+Alt+Q to stop parsing commands.")
    print("Press 'Shift+esc' to exit the script.")
    keyboard.wait('shift+esc')