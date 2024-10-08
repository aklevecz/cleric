# cleric



Assumptions: 
- you are targeting the guy you want to CH
- `go` (not case sensitive) is the operative word for the trigger

Will make these more flexible in the future

## Install

`install.bat`

This will install the dependencies and create the virtual env

### Potential install issues

If you have trouble installing the dependencies it may be one of the following issues
### Python version
I recomemnd using Python 3.10+, the install will fail with something around Python 3.7. You can check your version of python by running `python --version` in the terminal. You may need to find previously installed old versions of python and delete them before installing the newest version-- otherwise your computer may be confused and not use your latest version as `python`.

### C++ something
If you see this specific error while installing `ImportError: DLL load failed while importing _cext: The specified module could not be found` then you will need to install the [Latest supported Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170).

## Update

`update.bat`

This will pull down the latest from git and install dependencies if needed. No need to run the first time you install.

## Configuring health bars to watch

`configure-guy.bat`

Currently when you run this, you will need to close and restart the ui terminal window for it to update properly

This will prompt you for a reference for a healthbar to watch (e.g. `guy_name`, `xtar1`, `current_target`), and then will prompt you to draw a box around the health bar. Only the red part of their healthbar is important.

The bounding box for the healthbar is saved in `config.json`.

Any time a given healthbar is in a different position on your screen (as in your entire display, not just the EQ window), you will need to recreate the bounding boxes.

## UI

`ui.bat`

This will open a terminal window and web browser at http://127.0.0.1:7860 with the UI. If you close the terminal window the UI will stop functioning, but you can close the browser and reopen it again at the same url. The terminal window is running all of the python stuff, the browser is merely the UI interacting with it.

When you make a change in the UI and press Save Configuration, the `config.json` is updated. If you are parsing while you make a change, remember to stop and start parsing for those changes to take effect.

Currently, you will need to remember to press Save Configuration after any change besides the Word Bindings.

## Auto boot

`configure-eq-boot.bat`

Find the location of your Launch file and copy it, then run the above batch file. First you will provide the path, and then you will go through mouse clicks or pressing enter going through the process of logging in. Press Esc when you're done, and then input delays in seconds for each action.

`eq-boot.bat`

To run the automation that you recorded, run the batch file above.

## Below are Batch scripts that you can use instead of the UI, but the UI is recommended.

## Editing the Config with batch files instead of UI
### Configure abitrary bindings
`configure-log-file.bat`
- This will prompt you for the path to your log file (e.g. `C:\User\Public\blahblahblah\rw_guy_name_waiter.txt`)

`configure-word-binding.bat`
- This will prompt you for a string to parse in the logs, and a key binding to press when that string is present (e.g. `assist me guys!`, 6)

### Additional configuration for CH Chaining
`configure-match-words.bat` (Only neccessary for CH Chaining)
- This will prompt you to add a match word to your config. Currently as applied to chaining your match word would be the same as your audio trigger (e.g. `go guy_name`). It is not case sensitive.



This is what an example functioning config looks like with three potential guys to watch

```
{
    "bounding_boxes": {
        "guy_name": {
            "left": 1452.0,
            "top": 649.0,
            "width": 161.0,
            "height": 12.0
        }
    },
    "log_file": "C:\\Users\\Public\\Game Company\\Installed Games\\LemonQuest\\Logs\\lemonlog_Grok_tweeker.txt",
    "match_words": [
        "go guy_name"
    ],
    "default_guy": "guy_name",
    "ch_threshold": 90,
    "heal_threshold": 50,
    "heal_binding": "",
    "word_bindings": {
        "assist": "shift+x",
        "heal": "2",
        "target": "f",
        "zoom out": "mouse.scroll(0,-10000)",
        "zoom in and click": "mouse.scroll(0,10000);mouse.click();"
    }
}
```

## Run
`start.bat`  
This will open a command prompt window that will remain running while parsing  
The hotkeys are:  
- `Ctrl+Alt+s` to begin parsing. You will be asked for the `guy_name`'s health you are monitoring
- `Ctrl+Alt+q` to stop parsing, but leave the window open and available to start another parsing session  
- `Ctrl+Alt+c` to change the `guy_name` you are monitoring. Parsing will be paused and then restarted once you provide the guy.
- `Shift+esc` kill the script. You can also close the window


## Not using batch files

You can do everything from the commandline in a single window, including setting up the environment.

#### Installing dependencies (only needs to be run once)

`pip install -r requirements.txt`

#### Activating the environment (will need to be run whenever you open a new command window)
`env/Source/activate`


#### Running the various configuration commands
`python src/configure.py --create`

`python src/configure.py --log-file <LOG_FILE>`

`python src/configure.py --match-words <MATCH_WORD>`

`python src/configure.py --word-binding`

#### Starting the parsing
`python src/parse_logs.py`
