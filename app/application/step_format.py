"""Human-readable step titles/summaries and lightweight validation (UI + future MCP)."""

from __future__ import annotations

from pathlib import Path

from app.core.models import Action, ActionType, ClickPhase, MouseButton
from app.core.store import project_root


def format_step_title(action: Action) -> str:
    """Short English title for a workflow row."""
    titles = {
        ActionType.MOUSE_CLICK: "Mouse Click",
        ActionType.MOUSE_MOVE: "Mouse Move",
        ActionType.MOUSE_DRAG: "Mouse Drag",
        ActionType.KEY: "Press Key",
        ActionType.HOTKEY: "Hotkey",
        ActionType.HOLD: "Hold",
        ActionType.DELAY: "Wait",
        ActionType.FIND_TEXT: "Find Text & Click",
        ActionType.FIND_IMAGE: "Find Image & Click",
        ActionType.WAIT_TEXT: "Wait for Text",
        ActionType.WAIT_IMAGE: "Wait for Image",
        ActionType.IF_TEXT: "If Text",
        ActionType.IF_IMAGE: "If Image",
        ActionType.ELSE: "Else",
        ActionType.ENDIF: "End If",
    }
    return titles.get(action.type, action.type.value.replace("_", " ").title())


def format_step_summary(action: Action) -> str:
    """Secondary line for workflow rows (no emoji; delegate adds icon)."""
    if action.type == ActionType.MOUSE_CLICK:
        btn = (action.button or MouseButton.LEFT).value
        if action.click_phase == ClickPhase.DOWN:
            return f"{btn} down • ({action.x}, {action.y})"
        if action.click_phase == ClickPhase.UP:
            return f"{btn} up • ({action.x}, {action.y})"
        if action.click_count > 1:
            return f"{btn} ×{action.click_count} • ({action.x}, {action.y})"
        return f"Left click • ({action.x}, {action.y})" if btn == "left" else f"{btn} click • ({action.x}, {action.y})"
    if action.type == ActionType.MOUSE_MOVE:
        return f"Move to ({action.x}, {action.y})"
    if action.type == ActionType.MOUSE_DRAG:
        btn = (action.button or MouseButton.LEFT).value
        return f"{btn} ({action.x}, {action.y}) → ({action.end_x}, {action.end_y}) • {action.hold_ms} ms"
    if action.type == ActionType.KEY:
        key = action.key or "?"
        if action.key_phase.value == "down":
            return f"{key} (press)"
        if action.key_phase.value == "up":
            return f"{key} (release)"
        return key
    if action.type == ActionType.HOTKEY:
        return " + ".join(k.upper() for k in action.keys) or "(empty)"
    if action.type == ActionType.HOLD:
        target = action.key or f"mouse {(action.button or MouseButton.LEFT).value}"
        return f"{target} • {action.hold_ms} ms"
    if action.type == ActionType.DELAY:
        if action.delay_min_ms is not None and action.delay_max_ms is not None:
            return f"{action.delay_min_ms}–{action.delay_max_ms} ms"
        return f"{action.delay_ms} ms"
    if action.type == ActionType.FIND_TEXT:
        q = action.query or "…"
        return f'"{q}" • OCR • {action.timeout_ms // 1000}s{action.capture_summary()}'
    if action.type == ActionType.WAIT_TEXT:
        q = action.query or "…"
        return f'"{q}" • {action.timeout_ms} ms{action.capture_summary()}'
    if action.type == ActionType.FIND_IMAGE:
        name = Path(action.image_path).name if action.image_path else "…"
        return f"{name} • {action.threshold:.2f}{action.capture_summary()}"
    if action.type == ActionType.WAIT_IMAGE:
        name = Path(action.image_path).name if action.image_path else "…"
        return f"{name} • {action.timeout_ms} ms"
    if action.type == ActionType.IF_TEXT:
        q = action.query or "…"
        return f'"{q}"{action.capture_summary()}'
    if action.type == ActionType.IF_IMAGE:
        name = Path(action.image_path).name if action.image_path else "…"
        return f"{name} • {action.threshold:.2f}{action.capture_summary()}"
    if action.type == ActionType.ELSE:
        return "Else branch"
    if action.type == ActionType.ENDIF:
        return "Close condition"
    return action.type.value


def _resolve_image_path(image_path: str) -> Path | None:
    """Resolve template path relative to project root when needed."""
    if not image_path:
        return None
    p = Path(image_path)
    if p.is_file():
        return p
    for base in (project_root(), project_root() / "templates"):
        candidate = base / image_path
        if candidate.is_file():
            return candidate
    return None


def validate_step(action: Action) -> str | None:
    """Return a user-facing validation message or None if OK."""
    if action.type in (
        ActionType.FIND_IMAGE,
        ActionType.WAIT_IMAGE,
        ActionType.IF_IMAGE,
    ):
        if not action.image_path.strip():
            return "No template image"
        if _resolve_image_path(action.image_path) is None:
            return "Template missing"
    if action.type in (ActionType.FIND_TEXT, ActionType.WAIT_TEXT, ActionType.IF_TEXT):
        if not (action.query or "").strip():
            return "No search text"
    return None
