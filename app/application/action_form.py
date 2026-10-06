"""Build and parse Action fields for the step inspector (shared with future MCP)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.core.models import Action, ActionType, ClickPhase, KeyPhase, MouseButton, OnFail

PHASE_CLICK = {"Click": "click", "Press": "down", "Release": "up"}
PHASE_KEY = {"Tap": "tap", "Press": "down", "Release": "up"}
BUTTON_LABELS = {"Left": "left", "Right": "right", "Middle": "middle"}
ON_FAIL_LABELS = {"Stop": "stop", "Continue": "continue"}
CLICK_PHASE_LABEL = {v: k for k, v in PHASE_CLICK.items()}
KEY_PHASE_LABEL = {v: k for k, v in PHASE_KEY.items()}
BUTTON_VALUE_LABEL = {v: k for k, v in BUTTON_LABELS.items()}
ON_FAIL_VALUE_LABEL = {v: k for k, v in ON_FAIL_LABELS.items()}

VISION_TYPES = {
    ActionType.FIND_TEXT,
    ActionType.FIND_IMAGE,
    ActionType.WAIT_TEXT,
    ActionType.WAIT_IMAGE,
    ActionType.IF_TEXT,
    ActionType.IF_IMAGE,
}


def action_to_form(action: Action) -> dict[str, str]:
    """Flatten an Action into string form fields for the inspector."""
    data: dict[str, str] = {
        "x": str(action.x or 0),
        "y": str(action.y or 0),
        "end_x": str(action.end_x or 0),
        "end_y": str(action.end_y or 0),
        "button": BUTTON_VALUE_LABEL.get((action.button or MouseButton.LEFT).value, "Left"),
        "key": action.key or "",
        "keys": "+".join(action.keys),
        "hold_ms": str(action.hold_ms or 500),
        "delay_ms": str(action.delay_ms or 100),
        "phase_click": CLICK_PHASE_LABEL.get(action.click_phase.value, "Click"),
        "phase_key": KEY_PHASE_LABEL.get(action.key_phase.value, "Tap"),
        "query": action.query or "",
        "image_path": action.image_path or "",
        "threshold": str(action.threshold),
        "timeout_ms": str(action.timeout_ms),
        "on_fail": ON_FAIL_VALUE_LABEL.get(action.on_fail.value, "Stop"),
        "region_x": str(action.region_x),
        "region_y": str(action.region_y),
        "region_w": str(action.region_w),
        "region_h": str(action.region_h),
        "capture_monitor": "" if action.capture_monitor is None else str(action.capture_monitor),
    }
    return data


def build_action_from_form(base: Action, fields: dict[str, str], action_type: ActionType) -> Action | str:
    """Return updated Action or an error message string."""

    def _int(key: str, default: int = 0) -> int:
        try:
            return int(str(fields.get(key, default)).strip())
        except ValueError:
            return default

    def _float(key: str, default: float = 0.85) -> float:
        try:
            return float(str(fields.get(key, default)).strip())
        except ValueError:
            return default

    kind = action_type
    if kind == ActionType.MOUSE_CLICK:
        phase_raw = PHASE_CLICK.get(fields.get("phase_click", "Click"), "click")
        return replace(
            base,
            type=kind,
            x=_int("x"),
            y=_int("y"),
            button=MouseButton(BUTTON_LABELS.get(fields.get("button", "Left"), "left")),
            click_phase=ClickPhase(phase_raw),
        )
    if kind == ActionType.MOUSE_MOVE:
        return replace(base, type=kind, x=_int("x"), y=_int("y"))
    if kind == ActionType.MOUSE_DRAG:
        return replace(
            base,
            type=kind,
            x=_int("x"),
            y=_int("y"),
            end_x=_int("end_x"),
            end_y=_int("end_y"),
            button=MouseButton(BUTTON_LABELS.get(fields.get("button", "Left"), "left")),
            hold_ms=max(1, _int("hold_ms", 500)),
        )
    if kind == ActionType.KEY:
        key = (fields.get("key") or "").strip()
        if not key:
            return "Enter a key name"
        phase_raw = PHASE_KEY.get(fields.get("phase_key", "Tap"), "tap")
        return replace(base, type=kind, key=key, key_phase=KeyPhase(phase_raw))
    if kind == ActionType.HOTKEY:
        raw = (fields.get("keys") or "").replace("+", " ")
        parts = [p.strip() for p in raw.split() if p.strip()]
        if not parts:
            return "Enter a hotkey like ctrl+c"
        return replace(base, type=kind, keys=parts)
    if kind == ActionType.HOLD:
        key = (fields.get("key") or "").strip()
        return replace(
            base,
            type=kind,
            key=key or None,
            button=MouseButton(BUTTON_LABELS.get(fields.get("button", "Left"), "left")) if not key else None,
            x=_int("x") if not key else None,
            y=_int("y") if not key else None,
            hold_ms=_int("hold_ms", 500),
        )
    if kind == ActionType.DELAY:
        return replace(base, type=kind, delay_ms=_int("delay_ms", 100))
    if kind in (ActionType.ELSE, ActionType.ENDIF):
        return replace(base, type=kind)
    cap_mon = fields.get("capture_monitor", "").strip()
    capture_monitor = int(cap_mon) if cap_mon else None
    region = {
        "capture_monitor": capture_monitor,
        "region_x": _int("region_x"),
        "region_y": _int("region_y"),
        "region_w": _int("region_w"),
        "region_h": _int("region_h"),
    }
    if kind in (ActionType.FIND_TEXT, ActionType.WAIT_TEXT, ActionType.IF_TEXT):
        query = (fields.get("query") or "").strip()
        if not query:
            return "Enter search text"
        return replace(
            base,
            type=kind,
            query=query,
            button=MouseButton(BUTTON_LABELS.get(fields.get("button", "Left"), "left")),
            timeout_ms=_int("timeout_ms", 5000),
            on_fail=OnFail(ON_FAIL_LABELS.get(fields.get("on_fail", "Stop"), "stop")),
            **region,
        )
    if kind in (ActionType.FIND_IMAGE, ActionType.WAIT_IMAGE, ActionType.IF_IMAGE):
        image_path = (fields.get("image_path") or "").strip()
        if not image_path:
            return "Choose a template image"
        return replace(
            base,
            type=kind,
            image_path=image_path,
            button=MouseButton(BUTTON_LABELS.get(fields.get("button", "Left"), "left")),
            threshold=_float("threshold", 0.85),
            timeout_ms=_int("timeout_ms", 5000),
            on_fail=OnFail(ON_FAIL_LABELS.get(fields.get("on_fail", "Stop"), "stop")),
            **region,
        )
    return f"Unsupported type: {kind.value}"


def browse_image_name(path: str) -> str:
    """Return display-friendly template name."""
    return Path(path).name if path else ""
