"""Standalone game boot/login automation.

Records a sequence of mouse clicks + Enter presses (with per-step delays) and
replays them to launch a program and click through its login. Saved to
boot_config.json next to this script.

This tool is INTENTIONALLY self-contained: it depends only on `pynput` and the
standard library, and imports nothing from the rest of the cleric project. You
can copy the whole `boot/` folder on its own and use it anywhere.

Usage:
    python boot.py --new     # record a new sequence, then run it
    python boot.py --run      # replay the saved sequence
    python boot.py            # interactive prompt (new/run)
"""

import argparse
import json
import os
import subprocess
import time

from pynput import keyboard, mouse

# Keep config next to this script so the tool is location-independent.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOT_CONFIG = os.path.join(SCRIPT_DIR, "boot_config.json")

actions = []


def on_click(x, y, button, pressed):
    if pressed:
        actions.append({"type": "click", "x": x, "y": y})
        print(f"Recorded mouse click at ({x}, {y})")


def on_press(key):
    if key == keyboard.Key.enter:
        actions.append({"type": "enter"})
        print("Recorded Enter key press")
    elif key == keyboard.Key.esc:
        return False  # stop the listener


def configure_automation():
    global actions
    actions = []

    program_path = input("Enter the full path to the program you want to launch: ")
    subprocess.Popen(program_path)

    print("\nNow, perform the actions you want to automate.")
    print("Click the mouse or press Enter where needed.")
    print("Press Esc when you're finished recording actions.")

    mouse_listener = mouse.Listener(on_click=on_click)
    keyboard_listener = keyboard.Listener(on_press=on_press)
    mouse_listener.start()
    keyboard_listener.start()
    keyboard_listener.join()  # wait for Esc
    mouse_listener.stop()

    for i in range(len(actions)):
        delay = float(input(f"Enter delay before action {i + 1} (in seconds): "))
        actions[i]["delay"] = delay

    config = {"program_path": program_path, "actions": actions}
    with open(BOOT_CONFIG, "w") as f:
        json.dump(config, f, indent=4)

    print(f"\nConfiguration saved to {BOOT_CONFIG}")
    return config


def run_automation(config):
    mouse_controller = mouse.Controller()
    keyboard_controller = keyboard.Controller()

    subprocess.Popen(config["program_path"])
    time.sleep(2)  # let the program open

    for action in config["actions"]:
        print("Performing action:", action)
        if "delay" in action:
            time.sleep(action["delay"])
        if action["type"] == "click":
            mouse_controller.position = (action["x"], action["y"])
            mouse_controller.click(mouse.Button.left)
        elif action["type"] == "enter":
            keyboard_controller.press(keyboard.Key.enter)
            keyboard_controller.release(keyboard.Key.enter)


def load_config(filename=BOOT_CONFIG):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    print(f"Configuration file {filename} not found. Run with --new first.")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Game boot/login automation")
    parser.add_argument("--run", action="store_true", help="Run the saved configuration")
    parser.add_argument("--new", action="store_true", help="Record a new configuration")
    args = parser.parse_args()

    if args.run:
        cfg = load_config()
        if cfg:
            run_automation(cfg)
    elif args.new:
        cfg = configure_automation()
        if cfg:
            run_automation(cfg)
    else:
        choice = input("Enter 'new' to record a new configuration or 'run' to use the saved one: ").lower()
        if choice == "new":
            cfg = configure_automation()
            if cfg:
                run_automation(cfg)
        elif choice == "run":
            cfg = load_config()
            if cfg:
                run_automation(cfg)
        else:
            print("Invalid choice. Run again and enter 'new' or 'run'.")
