import subprocess
import time
from pynput import mouse, keyboard
import json
import os
import argparse

def on_click(x, y, button, pressed):
    if pressed:
        actions.append({'type': 'click', 'x': x, 'y': y})
        print(f"Recorded mouse click at ({x}, {y})")

def on_press(key):
    if key == keyboard.Key.enter:
        actions.append({'type': 'enter'})
        print("Recorded Enter key press")
    elif key == keyboard.Key.esc:
        # Stop listener
        return False

def configure_automation():
    global actions
    actions = []

    program_path = input("Enter the full path to the program you want to launch: ")
    subprocess.Popen(program_path)

    print("\nNow, perform the actions you want to automate.")
    print("Click the mouse or press Enter where needed.")
    print("Press Esc when you're finished recording actions.")
    
    # Start listeners
    mouse_listener = mouse.Listener(on_click=on_click)
    keyboard_listener = keyboard.Listener(on_press=on_press)
    
    mouse_listener.start()
    keyboard_listener.start()
    
    keyboard_listener.join()  # Wait for Esc key
    mouse_listener.stop()
    
    # Add delays
    for i in range(len(actions)):
        if i < len(actions):
            delay = float(input(f"Enter delay before action {i+1} (in seconds): "))
            actions[i]['delay'] = delay
    
    # Save configuration
    config = {
        'program_path': program_path,
        'actions': actions
    }
    with open('boot_config.json', 'w') as f:
        json.dump(config, f, indent=4)
    
    print("\nConfiguration saved to boot_config.json")
    return config

def run_automation(config):
    mouse_controller = mouse.Controller()
    keyboard_controller = keyboard.Controller()
    
    # Open the program
    subprocess.Popen(config['program_path'])
    time.sleep(2)  # Wait for the program to open
    
    # Perform the series of actions
    for action in config['actions']:
        print("Performing action:", action) 
        if 'delay' in action:
            time.sleep(action['delay'])
        if action['type'] == 'click':
            mouse_controller.position = (action['x'], action['y'])
            mouse_controller.click(mouse.Button.left)
        elif action['type'] == 'enter':
            keyboard_controller.press(keyboard.Key.enter)
            keyboard_controller.release(keyboard.Key.enter)
       

def load_config(filename='boot_config.json'):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    else:
        print(f"Configuration file {filename} not found.")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automation Configuration and Runner")
    parser.add_argument('--run', action='store_true', help="Run the existing configuration")
    parser.add_argument('--new', action='store_true', help="Create a new configuration")
    args = parser.parse_args()

    if args.run:
        config = load_config()
        if config:
            run_automation(config)
    elif args.new:
        config = configure_automation()
    else:
        # If no arguments provided, ask for input
        choice = input("Enter 'new' to create a new configuration or 'run' to use an existing one: ").lower()
        
        if choice == 'new':
            config = configure_automation()
            run_automation(config)
        elif choice == 'run':
            config = load_config()
            if config:
                run_automation(config)
        else:
            print("Invalid choice. Please run the script again and enter 'new' or 'run'.")