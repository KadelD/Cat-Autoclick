# Cat Autoclick

Desktop macro recorder and player for Windows. Create multiple presets, record or build keyboard/mouse steps (including chords and holds), and target a specific monitor.

## Requirements

- Python 3.11+
- Windows recommended (pynput input injection)

## Setup

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

## Notes

- Some games or elevated apps block injected input — run Cat Autoclick as Administrator if needed.
- Recording ignores F8/F9/F10 so control keys are not stored as macro steps.
- Mouse coordinates are stored relative to the selected monitor.

## Project layout

```
main.py
app/
  core/   # models, store, monitors, recorder, player
  ui/     # CustomTkinter windows
presets/  # saved macros
```

## Phase 2 ideas

- OCR / find text on screen and click
- Image template matching
- Conditional wait (color/image)
- Tray icon and `.exe` packaging
