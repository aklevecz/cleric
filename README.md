# cleric

## Install

`install.bat`

- this will install the dependencies and create the virtual env

## Configure
`configure-guy.bat`

- This will prompt you for reference name for your guy (e.g. `guy_name`), and then will prompt you to draw a box around their health in xtar
- This saves the bounding box for the references healthbar in `config.json`
- Any time you move your xtar window, you will need to recreate the bounding boxes

`configure-log-file.bat`
- This will prompt you for the path to your log file (e.g. `C:\User\Public\blahblahblah\eq_guy_name_server.txt`)

`configure-match-words.bat`
- This will prompt you to add a match word to your config. Currently as applied to only CH chaining your match word would be the same as your audio trigger (e.g. `go guy_name`). It is not case sensitive

You can edit the `config.json` file to make changes if you prefer. Though it is unlikely you can update bounding boxes effectively without using that script.

This is what an example functioning config looks like with three potential guys to watch

```
{
    "guy_name": {
        "left": 1452.0,
        "top": 649.0,
        "width": 161.0,
        "height": 12.0
    },
    "other_guy_name": {
        "left": 1420.0,
        "top": 706.0,
        "width": 162.0,
        "height": 10.0
    },
    "other_other_guy_name": {
        "left": 1450.0,
        "top": 681.0,
        "width": 160.0,
        "height": 16.0
    },
    "log_file": "C:\\Users\\Public\\Daybreak Game Company\\Installed Games\\EverQuest\\Logs\\eqlog_Grok_teek.txt",
    "match_words": [
        "go guy_name",
        "kill guy_name"
    ]
}
```

## Run
`start.bat`

This will start the instance for log parsing. To begin parsing logs for commands, press `Crtl+Alt+s`. You will be asked for the `guy_name` you are watching, i.e. the bounding box for the xtar healthbar. If you would like to change guys you are watching, press `Ctrl+Alt+c` and then type in `other_guy_name`.


No batch files

`pip install -r requirements.txt`

`env/Source/activate`

`python configure.py --create`

`python configure.py --log-file <LOG_FILE>`

`python configure.py --match-words <MATCH_WORD>`

`python parse_logs.py`
