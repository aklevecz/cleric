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
    for (key, _), value in zip(flat_config, args):
        keys = key.split('.')
        d = config
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        if isinstance(value, str):
            value = strip_quotes(value.strip())
        if key == 'match_words':
            d[keys[-1]] = value.split('\n')
        elif is_bounding_box(d[keys[-1]]):
            d[keys[-1]] = {k: int(v) for k, v in zip(['left', 'top', 'width', 'height'], value)}
        else:
            d[keys[-1]] = value
    save_config(config)
    return "Configuration saved!"

def is_bounding_box(item):
    return isinstance(item, dict) and all(key in item for key in ['left', 'top', 'width', 'height'])

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
        return f"Added binding: {word} -> {binding}", gr.update(choices=list(config['word_bindings'].keys()))
    return "Please enter both word and binding", gr.update()

def remove_word_binding(config, word):
    print("WTF")
    print(config, word)
    if word in config['word_bindings']:
        del config['word_bindings'][word]
        save_config(config)
        return f"Removed binding for: {word}", gr.update(choices=list(config['word_bindings'].keys()))
    return f"Binding not found for: {word}", gr.update()

config = init_config()
flat_config = flatten_config(config)
components = []

with gr.Blocks() as demo:
    with gr.Row():
        with gr.Column():
            gr.Markdown("### General Settings")
            log_file = gr.Textbox(value=config['log_file'], label="Log File")
            components.append(('log_file', log_file))

            heal_threshold = gr.Number(value=config['heal_threshold'], label="Heal Threshold")
            components.append(('heal_threshold', heal_threshold))

            heal_binding = gr.Textbox(value=config['heal_binding'], label="Heal Binding")
            components.append(('heal_binding', heal_binding))

        # with gr.Column():
        #     gr.Markdown("### Guy Name Settings")
        #     with gr.Group():
        #         gr.Markdown("#### Position and Size")
        #         left = gr.Number(value=config['guy_name']['left'], label="Left")
        #         top = gr.Number(value=config['guy_name']['top'], label="Top")
        #         width = gr.Number(value=config['guy_name']['width'], label="Width")
        #         height = gr.Number(value=config['guy_name']['height'], label="Height")
        #     components.extend([
        #         ('guy_name.left', left), ('guy_name.top', top),
        #         ('guy_name.width', width), ('guy_name.height', height)
        #     ])
        with gr.Column():
            gr.Markdown("### Bounding Box Settings")
            for key, value in flat_config:
                if is_bounding_box(value):
                    gr.Markdown(f"#### {key}")
                    with gr.Group():
                        left = gr.Number(value=value['left'], label="Left")
                        top = gr.Number(value=value['top'], label="Top")
                        width = gr.Number(value=value['width'], label="Width")
                        height = gr.Number(value=value['height'], label="Height")
                    components.extend([
                        (f"{key}.left", left), (f"{key}.top", top),
                        (f"{key}.width", width), (f"{key}.height", height)
                    ])

        with gr.Column():
            gr.Markdown("### Word Settings")
            match_words = gr.Textbox(value="\n".join(config['match_words']), label="Match Words", lines=3)
            components.append(('match_words', match_words))

            gr.Markdown("#### Word Bindings")
            word_bindings_dropdown = gr.Dropdown(choices=list(config['word_bindings'].keys()), label="Existing Word Bindings")
            new_word = gr.Textbox(label="New Word")
            new_binding = gr.Textbox(label="New Binding")
            add_binding_button = gr.Button("Add New Binding")
            remove_binding_button = gr.Button("Remove Selected Binding")
            binding_status = gr.Textbox(label="Binding Status")

    with gr.Row():
        log_output = gr.TextArea(label="Log Output", interactive=False)

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
        inputs=[gr.State(config)] + [comp for _, comp in components],
        outputs=status_box
    )

    add_binding_button.click(
        add_word_binding,
        inputs=[gr.State(config), new_word, new_binding],
        outputs=[binding_status, word_bindings_dropdown]
    )

    remove_binding_button.click(
        remove_word_binding,
        inputs=[gr.State(config), word_bindings_dropdown],
        outputs=[binding_status, word_bindings_dropdown]
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
threading.Timer(1, open_browser).start()  # Open browser after 1 second
demo.launch(server_port=port)