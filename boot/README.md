# boot — standalone game login automation

A tiny, self-contained tool that records your launch + login clicks once and
replays them to open the game and log in automatically.

**It depends on nothing else in this repo** — only Python 3.10+ and the single
package `pynput`. You can copy this `boot/` folder on its own and it will work.

## Install (one package)

```
pip install -r requirements.txt
```

(or, if you don't want a global install: `python -m venv venv` then
`venv\Scripts\activate` then the pip command above.)

## Use

Record a new sequence (it launches the program, then you click/press Enter
through login, press **Esc** when done, then type the delay before each step):

```
python boot.py --new
```

Replay the saved sequence any time:

```
python boot.py --run
```

Double-clickers can use `record-boot.bat` (record) and `run-boot.bat` (replay).

Your recorded steps are saved to `boot_config.json` **next to this script**, so
the tool works no matter what folder you run it from.

## Notes / limits

- Clicks are replayed at the exact screen coordinates you recorded, so the game
  launcher/login windows must appear in the same place. Re-record (`--new`) if
  your resolution or window position changes.
- This only automates the launcher/login click-path; it does nothing in-game.
