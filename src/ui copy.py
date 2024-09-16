import gradio as gr
from configure import load_config, save_config, strip_quotes
import threading
import time
import webbrowser

# Import necessary functions from your existing script
from parse_logs import start_tail_keybinding, stop_tail, start_health_check_keybinding, get_logs

def init_config():
    return load_config()

def save_new_config(config, *args):
    flat_config = flatten_config(config)
    print(flat_config)
    for (key, _), value in zip(flat_config, args):
        keys = key.split('.')
        print(key)
        d = config
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        if isinstance(value, str):
            value = strip_quotes(value.strip())
        if key == 'match_words':
            d[keys[-1]] = value.split('\n')
        elif key == "log_file":
            print("HELLO")
            d[keys[-1]] = strip_quotes(value.strip())
        elif is_bounding_box(d[keys[-1]]):
            if isinstance(value, dict):
                # If value is already a dict, use it directly
                d[keys[-1]] = {k: int(v) for k, v in value.items()}
                print("FUCKER")
            elif isinstance(value, str):
                # If value is a string, try to parse it as a dict
                try:
                    value_dict = eval(value)
                    if isinstance(value_dict, dict):
                        d[keys[-1]] = {k: int(v) for k, v in value_dict.items()}
                    else:
                        raise ValueError(f"Invalid bounding box format for {key}: {value}")
                except:
                    raise ValueError(f"Invalid bounding box format for {key}: {value}")
            else:
                raise ValueError(f"Unexpected type for bounding box {key}: {type(value)}")
        else:
            d[keys[-1]] = value
    save_config(config)
    return "Configuration saved!"

def is_bounding_box(item):
    if isinstance(item, dict):
        try:
            item['left']
            print(item)
            return True
        except:
            print('no left')
    return False
    # return isinstance(item, dict) and all(key in item for key in ['left', 'top', 'width', 'height'])

def flatten_config(config, prefix=''):
    items = []
    for key, value in config.items():
        new_key = f"{prefix}.{key}" if prefix else key
        if is_bounding_box(value):
            items.append((new_key, value))
        elif isinstance(value, dict):
            items.extend(flatten_config(value, new_key))
        else:
            items.append((new_key, value))
    return items

def display_binding(config, word):
    if word in config['word_bindings']:
        return config['word_bindings'][word]
    return ""

def start_parsing():
    start_tail_keybinding()
    return "Log parsing started."

def stop_parsing():
    stop_tail()
    return "Log parsing stopped."

def start_heal():
    start_health_check_keybinding()
    return "Health check started."

def stop_heal():
    stop_tail()
    return "Health check stopped."

# def update_logs():
    # logs = get_logs()
    # return logs

def update_logs(current_logs):
    new_logs = get_logs()
    if current_logs != new_logs:
        return new_logs
    return current_logs

def add_word_binding(config, word, binding):
    if word and binding:
        config['word_bindings'][word] = binding
        save_config(config)
        bindings_list = [f"{k}: {v}" for k, v in config['word_bindings'].items()]
        return (
            f"Added binding: {word} -> {binding}",
            gr.update(choices=bindings_list, value=[]),
            "",
            "",
            "",
            config  # Return updated config
        )
    return "Please enter both word and binding", gr.update(), "", gr.update(), gr.update(), config

def remove_word_binding(config, selected_bindings):
    if not selected_bindings:
        return "No binding selected for removal", gr.update(), config

    removed = []
    for binding in selected_bindings:
        word = binding.split(':')[0].strip()
        if word in config['word_bindings']:
            del config['word_bindings'][word]
            removed.append(word)

    if removed:
        save_config(config)
        bindings_list = [f"{k}: {v}" for k, v in config['word_bindings'].items()]
        return (
            f"Removed binding(s) for: {', '.join(removed)}",
            gr.update(choices=bindings_list, value=[]),
            config  # Return updated config
        )
    return "No valid bindings selected for removal", gr.update(), config

def display_binding(selected_bindings):
    if selected_bindings:
        return selected_bindings[0].split(':', 1)[1].strip()
    return ""

config = init_config()
flat_config = flatten_config(config)
components = []

with gr.Blocks() as demo:
    config_state = gr.State(config)

    with gr.Tabs():
        with gr.TabItem("General Settings"):
            for key, value in flat_config:
                if key in ['log_file', 'heal_threshold', 'heal_binding']:
                    if isinstance(value, (int, float)):
                        component = gr.Number(value=value, label=key)
                    else:
                        component = gr.Textbox(value=value, label=key)
                    components.append((key, component))

        with gr.TabItem("Bounding Box Settings"):
            for key, value in flat_config:
                if is_bounding_box(value):
                    gr.Markdown(f"### {key}")
                    with gr.Group():
                        left = gr.Number(value=value['left'], label="Left")
                        top = gr.Number(value=value['top'], label="Top")
                        width = gr.Number(value=value['width'], label="Width")
                        height = gr.Number(value=value['height'], label="Height")
                    components.extend([
                        (f"{key}.left", left), (f"{key}.top", top),
                        (f"{key}.width", width), (f"{key}.height", height)
                    ])

        with gr.TabItem("Word Settings"):
            match_words = gr.Textbox(value="\n".join(config['match_words']), label="Match Words", lines=3)
            components.append(('match_words', match_words))

            gr.Markdown("### Word Bindings")
            bindings_list = [f"{k}: {v}" for k, v in config['word_bindings'].items()]
            word_bindings_list = gr.CheckboxGroup(choices=bindings_list, label="Existing Word Bindings", interactive=True)
            selected_binding_value = gr.Textbox(label="Selected Binding Value", interactive=False)
            
            with gr.Row():
                new_word = gr.Textbox(label="New Word")
                new_binding = gr.Textbox(label="New Binding")
            
            with gr.Row():
                add_binding_button = gr.Button("Add New Binding")
                remove_binding_button = gr.Button("Remove Selected Binding(s)")
            
            binding_status = gr.Textbox(label="Binding Status")

        with gr.TabItem("Log Output"):
            log_output = gr.TextArea(label="Log Output", interactive=False, autoscroll=True)

    with gr.Row():
        save_button = gr.Button("Save Configuration")
        status_box = gr.Textbox(label="Status")

    with gr.Row():
        start_parse_button = gr.Button("Start Log Parsing")
        stop_parse_button = gr.Button("Stop Log Parsing")
        parse_status = gr.Textbox(label="Parsing Status")

    with gr.Row():
        start_heal_button = gr.Button("Start Health Check")
        stop_heal_button = gr.Button("Stop Health Check")
        heal_status = gr.Textbox(label="Health Check Status")

    save_button.click(
        save_new_config,
        inputs=[config_state] + [comp for _, comp in components],
        outputs=status_box
    )

    add_binding_button.click(
        add_word_binding,
        inputs=[config_state, new_word, new_binding],
        outputs=[binding_status, word_bindings_list, selected_binding_value, new_word, new_binding, config_state]
    )

    remove_binding_button.click(
        remove_word_binding,
        inputs=[config_state, word_bindings_list],
        outputs=[binding_status, word_bindings_list, config_state]
    )

    word_bindings_list.change(
        display_binding,
        inputs=[word_bindings_list],
        outputs=selected_binding_value
    )

    start_parse_button.click(start_parsing, outputs=parse_status)
    stop_parse_button.click(stop_parsing, outputs=parse_status)
    start_heal_button.click(start_heal, outputs=heal_status)
    stop_heal_button.click(stop_heal, outputs=heal_status)

    demo.load(update_logs, None, log_output, every=1)

def open_browser():
    webbrowser.open(f"http://127.0.0.1:{port}")  # Use the correct port

# Launch the interface
port = 7860  # You can change this if needed
# threading.Timer(1, open_browser).start()  # Open browser after 1 second
demo.launch(server_port=port)