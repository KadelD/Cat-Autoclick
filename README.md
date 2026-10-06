# Cat Autoclick / Cat Automation Studio

**Desktop macro recorder & player for Windows** — record keyboard and mouse, build steps by hand, find text (Thai + English OCR) or images on screen, and branch with if/else.

The default UI is **Cat Automation Studio** (PySide6 IDE layout). The previous CustomTkinter UI remains available as `python main_ctk.py` during migration — see [`docs/MIGRATION_UI.md`](docs/MIGRATION_UI.md).

[![Release](https://img.shields.io/github/v/release/KadelD/Cat-Autoclick)](https://github.com/KadelD/Cat-Autoclick/releases)
[![License](https://img.shields.io/github/license/KadelD/Cat-Autoclick)](LICENSE)

> **v1.1.0** — humanized mouse playback via Win32 SendInput. Prefer **Windows**. macOS/Linux may run with extra input-permission setup.

---

## What it can do

| Area | Capabilities |
|------|----------------|
| **Presets** | Multiple named macros as JSON under `presets/` |
| **Record** | Capture clicks, moves, drags, keys, chords; double-click & drag as first-class steps |
| **Playback** | Play / pause / stop, loop (`0` = infinite), optional jitter |
| **Manual editor** | Add/edit/reorder steps side-by-side; Material Icons on rows |
| **Monitors** | Pick a display; coordinates stay monitor-local |
| **Vision — text** | `find_text` / `wait_text` / `if_text` via EasyOCR (Thai + English) |
| **Vision — image** | `find_image` / `wait_image` / `if_image` via OpenCV templates |
| **Regions** | Full monitor or drag a capture box (Pick…) per vision step |
| **Control flow** | Flat `if_*` → … → `else` → … → `endif` |
| **Mid-record OCR** | Hotkeys insert find/wait/if text steps while recording |
| **Settings** | Hotkeys, start minimized, hide window while recording, Windows auto-start, OCR on/off |
| **Packaging** | `run.bat` for daily use; `build_exe.bat` → one-folder Windows app |

---

## Quick start

### Option A — scripts (recommended, especially for OCR)

**Windows**

```bat
run.bat
```

Studio UI (PySide6): `python main.py` · Legacy UI: `python main_ctk.py`

**macOS / Linux** (input capture may need OS permissions)

```bash
chmod +x run.sh
./run.sh
```

### Option B — manual venv

```bash
git clone https://github.com/KadelD/Cat-Autoclick.git
cd Cat-Autoclick
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Use **Python 3.11 or 3.12** when possible (3.13+ may work; release builds are validated best on 3.11–3.12).

### Option C — Windows `.exe`

```bat
build_exe.bat
```

Output folder: `dist\CatAutoclick\` — copy the **entire** folder (includes `_internal\`).

| Next to the exe | Purpose |
|-----------------|---------|
| `presets\` | Saved macros (demo presets seeded on first run) |
| `templates\` | Image templates for find/wait/if image |
| `settings.json` | App settings after you open **Settings → Save** |

**OCR note:** EasyOCR + models make packaged builds large. For serious OCR work, use `run.bat`. The `.exe` is solid for record/play and image find; text OCR inside the exe is best-effort.

---

## How to use

### 1. Presets

- Left panel: create, rename, select presets.
- Choose **Monitor**, **Loops**, and **Jitter ms** at the top.
- Click **Save** to write JSON under `presets/`.

### 2. Record a macro

1. Select a preset → **Record** (default `Ctrl+F9`).
2. A floating **HUD** shows tips. Optionally the main window hides (`Hide window while recording` in Settings).
3. Perform your clicks and keys.
4. Stop with **Stop Rec** / `Ctrl+F9`, or **Stop** / `Ctrl+F10`.

While recording:

- **Plain keys** (including F-keys alone) are stored in the macro.
- **App hotkeys** (default Ctrl+F6…F10) are **not** recorded.
- **Ctrl+F6 / Ctrl+F7** — insert an OCR text step (full monitor or drag area). Recording pauses so the dialog isn’t captured.

Drags become one `mouse_drag` (start → end + duration) and replay at constant speed. Double-clicks use `click_count`.

### 3. Play

- **Play** (default `Ctrl+F8`) runs the selected preset.
- **Pause** / **Resume** while playing.
- **Stop** ends playback and recording and releases held keys/buttons.

### 4. Build steps manually

In **Add step** / **Edit step**:

| Friendly label | What it does |
|----------------|--------------|
| Mouse click / Move / Drag | Pointer actions |
| Press key / Hotkey chord / Hold | Keyboard (and hold mouse) |
| Wait (delay) | Fixed delay in ms |
| Find text & click | OCR → click first match |
| Find image & click | Template match → click |
| Wait for text / image | Block until visible or timeout |
| If text / If image | Branch condition |
| Else / End if | Branch markers |

Click a row to edit → **Save changes**. **Add action** always appends. Drag rows to reorder.

Vision steps support:

- Query / image path + threshold + timeout
- **on_fail**: `stop` or `continue`
- Capture: monitor + optional region (W/H `0` = full)

### 5. If / else example

```
if_text "Start"
  find_text "Continue"
else
  key Escape
endif
```

Sample presets: **Demo Find Text**, **Demo OCR Branch**, **Demo If Text**.

### 6. Settings

Toolbar → **Settings**:

| Setting | Default | Notes |
|---------|---------|--------|
| Hotkeys | Ctrl+F6…F10 | Play / Record / Stop / OCR full / OCR area |
| Start minimized | off | Launch iconified |
| Hide window while recording | on | HUD still visible |
| Launch with Windows | off | Current-user Run key (Windows) |
| Humanize mouse | on | Bezier path before click/move |
| Move ms / Curve / Hover ms | 220 / 0.35 / 60 | Duration, curve strength, dwell before click |
| Enable OCR | on | Off = no EasyOCR load; hide OCR types/hotkeys; skip text vision at play |

Image vision still works when OCR is off. Settings live in `settings.json` next to `presets/` (or next to the exe).

On Windows, mouse moves use **SendInput** (not `SetCursorPos`) so apps that require real cursor motion / hover can see the path. Turn Humanize off only if you want a single jump.

---

## Default hotkeys

| Shortcut | Action |
|----------|--------|
| `Ctrl+F8` | Play / stop playback |
| `Ctrl+F9` | Start / stop recording |
| `Ctrl+F10` | Stop everything |
| `Ctrl+F6` | While recording: OCR full monitor |
| `Ctrl+F7` | While recording: OCR area |

Change these in **Settings**. Matching chords are swallowed during record so they don’t pollute the macro.

---

## Tips & limits

- Some games or elevated apps block injected input — run as **Administrator** if needed.
- OCR can misread tiny or stylized fonts; prefer **find image** for fixed UI buttons.
- First OCR use downloads EasyOCR models (needs network once).
- Coordinates are relative to the selected monitor.
- This tool automates your own desktop workflows. Use it responsibly and only where you have permission.

---

## Project layout

```
main.py                 # entry
run.bat / run.sh        # launchers
build_exe.bat           # PyInstaller one-folder build
cat-autoclick.spec
app/
  core/                 # models, store, settings, recorder, player, vision, …
  ui/                   # CustomTkinter UI
presets/                # example + your macros
templates/              # image templates
assets/fonts/           # Material Icons
```

Agent notes for contributors: see [`AGENTS.md`](AGENTS.md).

---

## Building a release `.exe`

```bat
build_exe.bat
```

Requires runtime + build deps (`requirements.txt`, `requirements-build.txt`). Ship the whole `dist\CatAutoclick\` directory.

---

## Roadmap (ideas)

- System tray / close-to-tray  
- Import/export preset packs  
- Wait-for-color  
- Optional smaller “no-OCR” exe flavor  

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.  
Material Icons font: see [`assets/fonts/NOTICE.txt`](assets/fonts/NOTICE.txt).
