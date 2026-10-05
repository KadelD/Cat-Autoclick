# AGENTS.md — Cat Autoclick

Guidance for coding agents working in this repository.

## Stack

- Python 3.11+
- UI: CustomTkinter (`app/ui/`)
- Input: pynput (`app/core/player.py`, `app/core/recorder.py`)
- Displays: screeninfo (`app/core/monitors.py`)
- Persistence: JSON files in `presets/` via `app/core/store.py`
- Packaging: PyInstaller (`cat-autoclick.spec`, `build_exe.bat`)

## Commands

```bash
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Launchers:

```bat
run.bat
build_exe.bat
```

```bash
./run.sh
```

Build deps are in `requirements-build.txt` (PyInstaller). Output exe folder: `dist/CatAutoclick/`.

There is no separate typecheck/lint script yet; keep modules small and typed with modern Python annotations.

## Conventions

- Add a short docstring on each new function or feature module.
- Preset/action schemas live in `app/core/models.py` — update `to_dict` / `from_dict` together when fields change.
- Playback and recording must stay on background threads; UI updates go through `widget.after(0, ...)`.
- Stop must release held keys/buttons (`MacroPlayer._release_all`).
- Coordinates are monitor-local; convert with `to_global` / `to_local` in `monitors.py`.
- `project_root()` in `store.py` must keep working for both source runs and frozen `.exe` (presets next to the executable).
- Update this file and `README.md` when behavior, layout, or commands change.
