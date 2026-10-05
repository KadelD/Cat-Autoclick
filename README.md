# Cat Autoclick

Desktop macro recorder and player for Windows. Create multiple presets, record or build keyboard/mouse steps (including chords and holds), and target a specific monitor.

## Requirements

- Python 3.11+ (for source / script launch)
- Windows recommended (pynput input injection)

## Quick start (scripts)

**Windows**

```bat
run.bat
```

**macOS / Linux** (input capture may need permissions)

```bash
chmod +x run.sh
./run.sh
```

## Build Windows .exe

```bat
build_exe.bat
```

Output: `dist\CatAutoclick\CatAutoclick.exe`  
Copy the whole `dist\CatAutoclick\` folder if you move it. Presets are stored in `presets\` next to the exe.

## Manual setup

```bash
cd cat-autoclick
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Hotkeys

| Key | Action |
|-----|--------|
| F8  | Play / stop playback |
| F9  | Start / stop recording |
| F10 | Stop everything |

## Features (MVP)

- Multiple presets saved as JSON under `presets/`
- Add steps manually or record them
- Mouse click/move, key tap/down/up, hotkey chords, hold, delay
- Monitor selection (coordinates are relative to the chosen display)
- Loop count (`0` = infinite) and small random jitter
- Play / Pause / Stop on a background thread
- `run.bat` / `run.sh` launchers and PyInstaller `.exe` build

## Notes

- Some games or elevated apps block injected input — run Cat Autoclick as Administrator if needed.
- Recording ignores F8/F9/F10 so control keys are not stored as macro steps.
- Mouse coordinates are stored relative to the selected monitor.

## Project layout

```
main.py
run.bat / run.sh
build_exe.bat
cat-autoclick.spec
app/
  core/   # models, store, monitors, recorder, player
  ui/     # CustomTkinter windows
presets/  # saved macros
```

## Phase 2 ideas

- OCR / find text on screen and click
- Image template matching
- Conditional wait (color/image)
- Tray icon
