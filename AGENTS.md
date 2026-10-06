# AGENTS.md — Cat Autoclick

Guidance for coding agents working in this repository.

## Stack

- Python 3.11+
- UI: **PySide6** Cat Automation Studio (`app/ui/`) — legacy CustomTkinter in `app/ui_ctk/` (`main_ctk.py`)
- Application layer: `app/application/` (Qt controllers; UI must not call pynput/OCR directly). Workflow edits use `MacroController` + `step_format.py` / `workflow_ops.py` (MCP-ready).
- Input: pynput (`app/core/player.py`, `app/core/recorder.py`)
- Displays: screeninfo (`app/core/monitors.py`)
- Vision: EasyOCR Thai+English + OpenCV templates (`app/core/vision.py`), capture via `mss`
- Control flow: flat if/else/endif markers (`app/core/control_flow.py`)
- Persistence: JSON files in `presets/` via `app/core/store.py`
- App settings: `settings.json` via `app/core/settings.py` (hotkeys, window, auto-start, OCR gate)
- Templates: `templates/` next to project/exe
- Icons: PySide6 vector icons via `app/ui/styles/icons.py` (QPainter, no emoji). Legacy CTk still uses Material font in `app/ui_ctk/icons.py`.
- Design tokens: `app/ui/styles/tokens.py` + stylesheet; reusable widgets in `app/ui/widgets/`
- Packaging: PyInstaller (`cat-autoclick.spec`, `build_exe.bat`); version in `app/__init__.py`
- Release prep skill: `.cursor/skills/release-prep/SKILL.md` (audit → optimize → build)

## Commands

```bash
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py          # PySide6 studio
python main_ctk.py      # legacy CustomTkinter UI
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

Prefer Python **3.11–3.12** for release builds until newer versions are proven with PyInstaller.

There is no separate typecheck/lint script yet; keep modules small and typed with modern Python annotations.

Release prep (agent skill `release-prep`): audit checklist → safe packaging/hygiene fixes → `build_exe.bat` → draft release notes. Do not commit/tag unless the user asks.

## Conventions

- Add a short docstring on each new function or feature module.
- Preset/action schemas live in `app/core/models.py` — update `to_dict` / `from_dict` together when fields change.
- Playback and recording stay on background threads; PySide6 UI updates via signals / `QTimer.singleShot(0, ...)`. Legacy CTk uses `widget.after(0, ...)`.
- Stop must release held keys/buttons (`MacroPlayer._release_all`).
- Coordinates are monitor-local; convert with `to_global` / `to_local` in `monitors.py`.
- `project_root()` in `store.py` must keep working for both source runs and frozen `.exe` (presets next to the executable).
- Keep Actions and Add/Edit step side-by-side in `ActionEditor` so the action list never collapses when the form grows; Add step scrolls on its own column. Click a row to load it, then **Save changes**; **Add action** always appends a new step.
- Action type dropdown uses friendly English labels (`TYPE_LABELS`); UI copy stays English-only.
- Action rows support drag-and-drop reorder via pack_forget/repack; drag handlers bind once and update `_cat_index` (avoid rebinding every select). Selection refresh is color-only.
- Building a `.exe` does **not** make the UI smoother (same Tk loop); prefer `run.bat` for OCR. Smoothness comes from lighter list updates and batched record appends.
- Row visuals come from `app/ui/action_display.py` (Material Icons via `icons.py`; compact delay rows; keys/buttons use `emphasize`; coordinates and other extras go in `detail` and show via info + `HoverTip` in `tooltip.py`).
- Theme palette priority: black → navy → cyan → purple → white (`app/ui_ctk/theme.py`). PySide6 studio tokens: `app/ui/styles/tokens.py` (mockup blue accent `#3B82F6`).
- EasyOCR must stay lazy-loaded in `vision.py` (first use is slow / downloads models); honor `ocr_enabled` from `get_settings()` so Reader never constructs when off.
- Vision capture uses `CaptureSpec` (`capture_monitor` + `region_*`); hits stay monitor-local via crop offsets.
- Region picker UI: PySide6 `app/ui/overlays/region_picker.py`; legacy `app/ui_ctk/region_picker.py`.
- PySide6 settings: `app/ui/dialogs/settings_dialog.py`; OCR while recording: `app/ui/dialogs/ocr_capture_dialog.py`; record HUD: `app/ui/overlays/record_hud.py`.
- Step inspector: `app/ui/inspector/step_inspector.py` + `application/action_form.py`.
- Recorder captures drag as a single `mouse_drag` (start→end + total ms); playback moves at constant speed. Double-clicks use `click_count` on `Action`.
- App Settings UI: `app/ui/settings_dialog.py`; wire via `MainWindow._apply_settings` (rebuild `GlobalHotKeys`, button/HUD labels, `recorder.set_app_hotkeys`, `editor.set_ocr_enabled`).
- Mouse playback humanize (`humanize_mouse`, `mouse_move_ms`, `mouse_curve`, `mouse_hover_ms`): `MacroPlayer._move_to_global` uses Bezier + ease-in-out, Win32 `SendInput` absolute moves via `mouse_input.py` (not pynput `SetCursorPos`), optional approach-from-outside when already near target, then hover dwell before click.
- Recording shows `RecordHud` (`app/ui/overlays/record_hud.py`); `hide_on_record` / `hide_on_play` control main-window hide. App hotkeys come from settings (defaults Ctrl+F6…F10); plain keys remain recordable. OCR hotkeys → full/area + `OcrCaptureDialog` while `MacroRecorder.pause()`.
- When OCR is off: hide OCR types/hotkeys; player skips `find_text` / `wait_text` and treats `if_text` as false with a status message; image vision stays available.
- Windows auto-start uses HKCU `Run` value `CatAutoclick` (`apply_auto_start` in `settings.py`).
- If/else nesting is resolved by `find_if_block`; player skips else bodies via `skip_else_to_endif` map.
- Update this file and `README.md` when behavior, layout, or commands change.
