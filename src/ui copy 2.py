import gradio as gr
import json
import os
import threading
import time
import webbrowser

# ------------------------ Configuration Management ------------------------ #

CONFIG_FILE = 'config.json'

def load_config():
    print(f"LOADING CONFIG FROM {CONFIG_FILE}")
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "log_file": "",
            "heal_threshold": 0,
            "heal_binding": "",
            "default_guy": "badegg",
            "badegg": {"left": 0, "top": 0, "width": 0, "height": 0},
            "mollo": {"left": 0, "top": 0, "width": 0, "height": 0},
            "match_words": [],
            "word_bindings": {}
        }
        save_config(default_config)
        return default_config
    else:
        with open(CONFIG_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error parsing config.json: {e}")
                return {
                    "log_file": "",
                    "heal_threshold": 0,
                    "heal_binding": "",
                    "default_guy": "badegg",
                    "badegg": {"left": 0, "top": 0, "width": 0, "height": 0},
                    "mollo": {"left": 0, "top": 0, "width": 0, "height": 0},
                    "match_words": [],
                    "word_bindings": {}
                }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print("Configuration saved successfully.")

def get_word_bindings_list(word_bindings):
    return [f"{k}: {v}" for k, v in word_bindings.items()]

def parse_word_bindings_list(bindings_list):
    bindings = {}
    for item in bindings_list:
        if ':' in item:
            key, value = item.split(':', 1)
            bindings[key.strip()] = value.strip()
    return bindings

# ------------------------ Log Parsing Functions ------------------------ #

# def start_tail_keybinding():
#     print("Started tail keybinding.")

# def stop_tail():
#     print("Stopped tail.")

# def start_health_check_keybinding():
#     print("Started health check keybinding.")

# def get_logs():
#     return "Sample log output...\nAnother log line."

from parse_logs import start_tail_keybinding, stop_tail, start_health_check_keybinding, get_logs

# ------------------------ UI Creation ------------------------ #
def is_bounding_box(item):
    """Check if an item has the structure of a bounding box."""
    return isinstance(item, dict) and set(item.keys()) == {"left", "top", "width", "height"}

def create_bounding_box_ui(label):
    """Create UI components for a bounding box."""
    with gr.Column():
        gr.Markdown(f"### {label} Bounding Box")
        left = gr.Number(label="Left", precision=0)
        top = gr.Number(label="Top", precision=0)
        width = gr.Number(label="Width", precision=0)
        height = gr.Number(label="Height", precision=0)
    return {"left": left, "top": top, "width": width, "height": height}

def create_ui():
    initial_config = load_config()
    
    with gr.Blocks(css=".gradio-container {max-width: 800px; margin: auto;}") as demo:
        config_state = gr.State(value=initial_config)
        ui_components = {}
        with gr.Tabs():
            with gr.TabItem("General Settings"):
                with gr.Column():
                    log_file = gr.Textbox(label="Log File Path", placeholder="Enter log file path", lines=1)
                    heal_threshold = gr.Number(label="Heal Threshold", precision=0)
                    heal_binding = gr.Textbox(label="Heal Binding", placeholder="Enter heal binding key", lines=1)
                    default_guy = gr.Dropdown(label="Default Guy", choices=["badegg", "mollo"])
                with gr.TabItem("Bounding Box Settings"):
                    for key, value in initial_config.items():
                        if is_bounding_box(value):
                            ui_components[key] = create_bounding_box_ui(key.capitalize())
            # with gr.TabItem("Bounding Box Settings"):
            #     with gr.Column():
            #         gr.Markdown("### Badegg Bounding Box")
            #         badegg_left = gr.Number(label="Left", precision=0)
            #         badegg_top = gr.Number(label="Top", precision=0)
            #         badegg_width = gr.Number(label="Width", precision=0)
            #         badegg_height = gr.Number(label="Height", precision=0)
                    
            #         gr.Markdown("### Mollo Bounding Box")
            #         mollo_left = gr.Number(label="Left", precision=0)
            #         mollo_top = gr.Number(label="Top", precision=0)
            #         mollo_width = gr.Number(label="Width", precision=0)
            #         mollo_height = gr.Number(label="Height", precision=0)
        
            with gr.TabItem("Word Settings"):
                with gr.Column():
                    match_words = gr.Textbox(label="Match Words", placeholder="Enter one word per line", lines=5)
                    
                    gr.Markdown("### Word Bindings")
                    word_bindings_list = gr.CheckboxGroup(label="Existing Word Bindings")
                    selected_binding_value = gr.Textbox(label="Selected Binding Value", interactive=False, lines=1)
                    
                    with gr.Row():
                        new_word = gr.Textbox(label="New Word", placeholder="Enter new word", lines=1)
                        new_binding = gr.Textbox(label="New Binding", placeholder="Enter binding for the new word", lines=1)
                    
                    with gr.Row():
                        add_binding_button = gr.Button("Add Binding")
                        remove_binding_button = gr.Button("Remove Selected Binding(s)")
                    
                    binding_status = gr.Textbox(label="Binding Status", interactive=False, lines=1)
        
            with gr.TabItem("Log Output"):
                log_output = gr.TextArea(label="Log Output", interactive=False, lines=20)
        
        with gr.Row():
            save_button = gr.Button("Save Configuration")
            status_box = gr.Textbox(label="Status", interactive=False, lines=1)
        
        with gr.Row():
            start_parse_button = gr.Button("Start Log Parsing")
            stop_parse_button = gr.Button("Stop Log Parsing")
            parse_status = gr.Textbox(label="Parsing Status", interactive=False, lines=1)
        
        with gr.Row():
            start_heal_button = gr.Button("Start Health Check")
            stop_heal_button = gr.Button("Stop Health Check")
            heal_status = gr.Textbox(label="Health Check Status", interactive=False, lines=1)
        
        def load_config_ui(config):
            print(f"Loading UI with config: {config}")
            return {
                log_file: config.get("log_file", ""),
                heal_threshold: config.get("heal_threshold", 0),
                heal_binding: config.get("heal_binding", ""),
                default_guy: config.get("default_guy", "badegg"),
                badegg_left: config.get("badegg", {}).get("left", 0),
                badegg_top: config.get("badegg", {}).get("top", 0),
                badegg_width: config.get("badegg", {}).get("width", 0),
                badegg_height: config.get("badegg", {}).get("height", 0),
                mollo_left: config.get("mollo", {}).get("left", 0),
                mollo_top: config.get("mollo", {}).get("top", 0),
                mollo_width: config.get("mollo", {}).get("width", 0),
                mollo_height: config.get("mollo", {}).get("height", 0),
                match_words: "\n".join(config.get("match_words", [])),
                word_bindings_list: gr.update(choices=get_word_bindings_list(config.get("word_bindings", {})))
            }

        def save_configuration(
            config,
            log_file_val,
            heal_threshold_val,
            heal_binding_val,
            default_guy_val,
            badegg_left_val,
            badegg_top_val,
            badegg_width_val,
            badegg_height_val,
            mollo_left_val,
            mollo_top_val,
            mollo_width_val,
            mollo_height_val,
            match_words_val
        ):
            try:
                new_config = {
                    "log_file": log_file_val.strip(),
                    "heal_threshold": int(heal_threshold_val),
                    "heal_binding": heal_binding_val.strip(),
                    "default_guy": default_guy_val,
                    "badegg": {
                        "left": int(badegg_left_val),
                        "top": int(badegg_top_val),
                        "width": int(badegg_width_val),
                        "height": int(badegg_height_val)
                    },
                    "mollo": {
                        "left": int(mollo_left_val),
                        "top": int(mollo_top_val),
                        "width": int(mollo_width_val),
                        "height": int(mollo_height_val)
                    },
                    "match_words": [word.strip() for word in match_words_val.split('\n') if word.strip()],
                    "word_bindings": config.get("word_bindings", {})
                }
                save_config(new_config)
                return "Configuration saved successfully.", new_config
            except Exception as e:
                return f"Error saving configuration: {e}", config

        def add_binding_handler(config, word, binding):
            if not word or not binding:
                return "Please enter both word and binding.", gr.update(), config
            config['word_bindings'][word.strip()] = binding.strip()
            save_config(config)
            new_bindings = get_word_bindings_list(config['word_bindings'])
            return f"Added binding: {word} -> {binding}", gr.update(choices=new_bindings), config

        def remove_binding_handler(config, selected_bindings):
            if not selected_bindings:
                return "No bindings selected for removal.", gr.update(), config
            removed = []
            for binding in selected_bindings:
                if ':' in binding:
                    word, _ = binding.split(':', 1)
                    word = word.strip()
                    if word in config['word_bindings']:
                        del config['word_bindings'][word]
                        removed.append(word)
            save_config(config)
            new_bindings = get_word_bindings_list(config['word_bindings'])
            return f"Removed binding(s) for: {', '.join(removed)}", gr.update(choices=new_bindings), config

        def display_binding_handler(selected_bindings):
            if not selected_bindings:
                return ""
            binding = selected_bindings[0]
            if ':' in binding:
                return binding.split(':', 1)[1].strip()
            return ""

        def start_parsing():
            try:
                start_tail_keybinding()
                return "Log parsing started."
            except Exception as e:
                return f"Failed to start parsing: {e}"

        def stop_parsing():
            try:
                stop_tail()
                return "Log parsing stopped."
            except Exception as e:
                return f"Failed to stop parsing: {e}"

        def start_heal():
            try:
                start_health_check_keybinding()
                return "Health check started."
            except Exception as e:
                return f"Failed to start health check: {e}"

        def stop_heal():
            try:
                stop_tail()
                return "Health check stopped."
            except Exception as e:
                return f"Failed to stop health check: {e}"

        save_button.click(
            save_configuration,
            inputs=[
                config_state,
                log_file,
                heal_threshold,
                heal_binding,
                default_guy,
                badegg_left,
                badegg_top,
                badegg_width,
                badegg_height,
                mollo_left,
                mollo_top,
                mollo_width,
                mollo_height,
                match_words
            ],
            outputs=[status_box, config_state]
        )

        add_binding_button.click(
            add_binding_handler,
            inputs=[config_state, new_word, new_binding],
            outputs=[binding_status, word_bindings_list, config_state]
        )

        remove_binding_button.click(
            remove_binding_handler,
            inputs=[config_state, word_bindings_list],
            outputs=[binding_status, word_bindings_list, config_state]
        )

        word_bindings_list.change(
            display_binding_handler,
            inputs=[word_bindings_list],
            outputs=selected_binding_value
        )

        start_parse_button.click(start_parsing, inputs=[], outputs=parse_status)
        stop_parse_button.click(stop_parsing, inputs=[], outputs=parse_status)
        start_heal_button.click(start_heal, inputs=[], outputs=heal_status)
        stop_heal_button.click(stop_heal, inputs=[], outputs=heal_status)

        demo.load(
            fn=load_config_ui,
            inputs=[config_state],
            outputs=[
                log_file, heal_threshold, heal_binding, default_guy,
                badegg_left, badegg_top, badegg_width, badegg_height,
                mollo_left, mollo_top, mollo_width, mollo_height,
                match_words, word_bindings_list
            ]
        )
        def update_logs(current_logs):
            new_logs = get_logs()
            if current_logs != new_logs:
                return new_logs
            return current_logs
        demo.load(update_logs, None, log_output, every=1)

        return demo

# ------------------------ Launch Interface ------------------------ #

def open_browser(port):
    time.sleep(1)
    webbrowser.open(f"http://127.0.0.1:{port}")

# ------------------------ Main Execution ------------------------ #

if __name__ == "__main__":
    demo = create_ui()
    port = 7860
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    demo.launch(server_port=port)