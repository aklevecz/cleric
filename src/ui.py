import gradio as gr
import json
import os
import threading
import time
import webbrowser
from configure import load_config, save_config
from parse_logs import start_tail_keybinding, stop_tail, start_health_check_keybinding, get_logs

initial_config = None  # Declare initial_config globally
selected_binding_value = []
# def save_config(config):
#     with open(CONFIG_FILE, 'w') as f:
#         json.dump(config, f, indent=4)
#     print("Configuration saved successfully.")

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


# ------------------------ UI Creation ------------------------ #

def create_ui():
    global initial_config
    global selected_binding_value
    initial_config = load_config()

    with gr.Blocks(css=".gradio-container {max-width: 800px; margin: auto;}") as demo:
        config_state = gr.State(load_config())
        all_components = []

        # Extract bounding box keys from the initial configuration
        bounding_box_keys = sorted(initial_config.get('bounding_boxes', {}).keys())

        with gr.Tabs():
            with gr.TabItem("General Settings"):
                with gr.Column():
                    log_file = gr.Textbox(label="Log File Path", placeholder="Enter log file path", lines=1)
                    default_guy = gr.Dropdown(label="Default Guy", choices=bounding_box_keys)
                    ch_threshold = gr.Number(label="CH Threshold", precision=0)
                    all_components.extend([log_file, default_guy, ch_threshold])

            with gr.TabItem("Auto Heal Settings"):
                with gr.Column():
                    heal_threshold = gr.Number(label="Heal Threshold", precision=0)
                    heal_binding = gr.Textbox(label="Heal Binding", placeholder="Enter heal binding key", lines=1)
                    all_components.extend([heal_threshold, heal_binding])

            with gr.TabItem("Bounding Box Settings"):
                bounding_boxes = {}
                for key in bounding_box_keys:
                    with gr.Column():
                        gr.Markdown(f"### {key.capitalize()} Bounding Box")
                        left = gr.Number(label="Left", precision=0)
                        top = gr.Number(label="Top", precision=0)
                        width = gr.Number(label="Width", precision=0)
                        height = gr.Number(label="Height", precision=0)
                        bounding_boxes[key] = {"left": left, "top": top, "width": width, "height": height}
                        all_components.extend([left, top, width, height])

            with gr.TabItem("Word Settings"):
                with gr.Column():
                    match_words = gr.Textbox(label="Match Words", placeholder="Enter one word per line", lines=5)
                    all_components.append(match_words)

                    gr.Markdown("### Word Bindings")
                    word_bindings_list = gr.CheckboxGroup(label="Existing Word Bindings")
                    all_components.extend([word_bindings_list])

                    with gr.Row():
                        new_word = gr.Textbox(label="New Word", placeholder="Enter new word", lines=1)
                        new_binding = gr.Textbox(label="New Binding", placeholder="Enter binding for the new word", lines=1)
                    all_components.extend([new_word, new_binding])

                    with gr.Row():
                        add_binding_button = gr.Button("Add Binding")
                        remove_binding_button = gr.Button("Remove Selected Binding(s)")

                    binding_status = gr.Textbox(label="Binding Status", interactive=False, lines=1)
                    all_components.append(binding_status)

            with gr.TabItem("Log Output"):
                log_output = gr.TextArea(label="Log Output", interactive=False, lines=20)
                all_components.append(log_output)

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

        def load_config_ui():
            config = load_config()
            outputs = []

            # General Settings
            outputs.append(config.get("log_file", ""))
            bounding_box_keys = sorted(config.get('bounding_boxes', {}).keys())
            default_guy_value = config.get("default_guy", "")

            if default_guy_value not in bounding_box_keys:
                default_guy_value = bounding_box_keys[0] if bounding_box_keys else ""
            outputs.append(gr.update(choices=bounding_box_keys, value=default_guy_value))

            outputs.append(config.get("ch_threshold", 90))
            # Auto Heal Settings
            outputs.append(config.get("heal_threshold", 0))
            outputs.append(config.get("heal_binding", ""))

            # Bounding Box Settings
            for key in bounding_box_keys:
                bbox = config['bounding_boxes'].get(key, {})
                outputs.append(bbox.get("left", 0))
                outputs.append(bbox.get("top", 0))
                outputs.append(bbox.get("width", 0))
                outputs.append(bbox.get("height", 0))

            # Word Settings
            outputs.append("\n".join(config.get("match_words", [])))
            word_bindings = config.get("word_bindings", {})
            outputs.append(gr.update(choices=get_word_bindings_list(word_bindings), value=[]))
            outputs.append("")  # selected_binding_value
            outputs.append("")  # new_word
            outputs.append("")  # new_binding
            outputs.append("")  # binding_status

            # Log Output
            outputs.append(get_logs())

            return outputs

        def save_configuration(config, *args):
            try:
                new_config = config.copy()
                arg_index = 0

                # General Settings
                new_config["log_file"] = args[arg_index]
                arg_index += 1
                new_config["default_guy"] = args[arg_index]
                arg_index += 1
                new_config["ch_threshold"] = args[arg_index]
                arg_index += 1

                # Auto Heal Settings
                new_config["heal_threshold"] = args[arg_index]
                arg_index += 1
                new_config["heal_binding"] = args[arg_index]
                arg_index += 1

                # Bounding Box Settings
                bounding_box_keys = sorted(config.get('bounding_boxes', {}).keys())
                new_config['bounding_boxes'] = {}

                for key in bounding_box_keys:
                    new_config['bounding_boxes'][key] = {
                        "left": int(args[arg_index]),
                        "top": int(args[arg_index + 1]),
                        "width": int(args[arg_index + 2]),
                        "height": int(args[arg_index + 3])
                    }
                    arg_index += 4

                # Word Settings
                match_words_val = args[arg_index]
                arg_index += 1
                new_config["match_words"] = [word.strip() for word in match_words_val.split('\n') if word.strip()]

                # Preserve word_bindings
                new_config["word_bindings"] = config.get("word_bindings", {})

                # Save the new configuration
                save_config(new_config)
                return new_config, "Configuration saved successfully."
            except Exception as e:
                return config, f"Error saving configuration: {e}"

        def add_binding_handler(config, word, binding):
            if not word or not binding:
                return config, "Please enter both word and binding.", gr.update()
            new_config = config.copy()
            new_config['word_bindings'][word.strip()] = binding.strip()
            new_bindings = get_word_bindings_list(new_config['word_bindings'])
            save_config(new_config)
            return new_config, f"Added binding: {word} -> {binding}", gr.update(choices=new_bindings, value=[])

        def remove_binding_handler(config, selected_bindings):
            if not selected_bindings:
                return config, "No bindings selected for removal.", gr.update()
            new_config = config.copy()
            removed = []
            for binding in selected_bindings:
                if ':' in binding:
                    word, _ = binding.split(':', 1)
                    word = word.strip()
                    if word in new_config['word_bindings']:
                        del new_config['word_bindings'][word]
                        removed.append(word)
            save_config(new_config)
            new_bindings = get_word_bindings_list(new_config['word_bindings'])
            return new_config, f"Removed binding(s) for: {', '.join(removed)}", gr.update(choices=new_bindings, value=[])

        def display_binding_handler(selected_bindings):
            print(selected_bindings)
            if not selected_bindings:
                return ""
            binding = selected_bindings[0]
            if ':' in binding:
                return binding.split(':', 1)[0].strip()
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
            inputs=[config_state] + all_components[:-1],
            outputs=[config_state, status_box]
        )

        add_binding_button.click(
            add_binding_handler,
            inputs=[config_state, new_word, new_binding],
            outputs=[config_state, binding_status, word_bindings_list]
        )

        remove_binding_button.click(
            remove_binding_handler,
            inputs=[config_state, word_bindings_list],
            outputs=[config_state, binding_status, word_bindings_list]
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
            inputs=None,
            outputs=all_components
        )

        demo.load(fn=get_logs, inputs=None, outputs=log_output, every=1)

        return demo

    return demo

# ------------------------ Launch Interface ------------------------ #

def open_browser(port):
    time.sleep(1)
    webbrowser.open(f"http://127.0.0.1:{port}")

# ------------------------ Main Execution ------------------------ #
import argparse
import socket
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UI Options")
    parser.add_argument('--host', type=str, default="127.0.0.1", help="Host IP address")
    parser.add_argument('--share', action='store_true', help="Share the interface")
    args = parser.parse_args()
    demo = create_ui()
    port = 7860
    if args.host == '0.0.0.0':
        print(f"You can open the UI on another device with this url: http://{get_local_ip()}:{port}")
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    demo.launch(server_name=args.host, server_port=port, share=args.share)
