# PySide6 UI migration map

## Current core (unchanged)

| Module | Role |
|--------|------|
| `app/core/models.py` | `Preset`, `Action`, enums |
| `app/core/store.py` | JSON presets |
| `app/core/recorder.py` | Input capture |
| `app/core/player.py` | Playback + vision steps + `on_step` highlight |
| `app/core/vision.py` | OCR / template |
| `app/core/settings.py` | `settings.json` |
| `app/core/control_flow.py` | Flat if/else/endif |
| `app/core/monitors.py` | Monitor list / coords |
| `app/core/mouse_input.py` | Win32 SendInput moves |

## Legacy UI → replacement

| CustomTkinter (`app/ui_ctk/`) | PySide6 (`app/ui/`) |
|------------------------------|---------------------|
| `main_window.py` | `main_window.py` + `application/app_controller.py` |
| `preset_panel.py` | `layout/sidebar.py` |
| `action_editor.py` | `workflow/*` + `inspector/step_inspector.py` + `dialogs/add_step_palette.py` |
| `action_display.py` | `application/step_format.py` + workflow model/delegate |
| `settings_dialog.py` | `dialogs/settings_dialog.py` |
| `record_hud.py` | `overlays/record_hud.py` |
| `region_picker.py` | `overlays/region_picker.py` |
| `ocr_capture_dialog.py` | `dialogs/ocr_capture_dialog.py` (Phase 6 — pending) |
| `theme.py` | `styles/tokens.py` + `styles/stylesheet.py` |

## Application controllers

UI talks to `app/application/*` only for record/play/save/hotkeys — not to pynput/OCR directly.

Workflow mutations: `MacroController` (`add_step`, `update_step`, `delete_step`, `duplicate_step`, `move_step`, `validate_workflow`, undo stack).

Form helpers: `application/action_form.py`, `application/step_format.py`.

## Preset JSON

No schema change. Flat `actions[]` with if/else/endif markers preserved.

## Phase status (2026)

| Phase | Status |
|-------|--------|
| 0 Audit + map | Done |
| 1 Foundation | Done |
| 2 Presets sidebar | Done |
| 3 Workflow editor | Done — tree, DnD, undo, palette, if/else |
| 4 Inspector | Done — type-aware form, save, region pick, delete |
| 5 Record HUD | Done — Qt HUD wired |
| 6 Playback highlight | Done — `on_step` → workflow row |
| 7 Region picker | Done — Qt overlay |
| 8 Settings | Done — Qt dialog + apply |
| 9 OCR capture | Done — `dialogs/ocr_capture_dialog.py` + hotkeys while recording |
| 9.5 UI redesign | Done — design tokens, vector icons (no emoji), polished shell/workflow/inspector |

Run: `python main.py` (Cat Automation Studio) · `python main_ctk.py` (legacy UI, optional).
