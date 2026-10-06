"""Default Action instances for new workflow steps."""

from __future__ import annotations

from uuid import uuid4

from app.core.models import Action, ActionType, ClickPhase, KeyPhase, MouseButton


def new_action_id() -> str:
    """Generate a fresh action id."""
    return uuid4().hex[:10]


def default_action(action_type: ActionType) -> Action:
    """Create a new step with sensible defaults for the editor."""
    aid = new_action_id()
    if action_type == ActionType.MOUSE_CLICK:
        return Action(
            type=action_type,
            id=aid,
            x=100,
            y=100,
            button=MouseButton.LEFT,
            click_phase=ClickPhase.CLICK,
        )
    if action_type == ActionType.MOUSE_MOVE:
        return Action(type=action_type, id=aid, x=100, y=100)
    if action_type == ActionType.MOUSE_DRAG:
        return Action(
            type=action_type,
            id=aid,
            x=100,
            y=100,
            end_x=200,
            end_y=200,
            button=MouseButton.LEFT,
            hold_ms=300,
        )
    if action_type == ActionType.KEY:
        return Action(type=action_type, id=aid, key="a", key_phase=KeyPhase.TAP)
    if action_type == ActionType.HOTKEY:
        return Action(type=action_type, id=aid, keys=["ctrl", "c"])
    if action_type == ActionType.HOLD:
        return Action(type=action_type, id=aid, key="shift", hold_ms=500)
    if action_type == ActionType.DELAY:
        return Action(type=action_type, id=aid, delay_ms=500)
    if action_type == ActionType.FIND_TEXT:
        return Action(type=action_type, id=aid, query="Continue", timeout_ms=5000)
    if action_type == ActionType.FIND_IMAGE:
        return Action(type=action_type, id=aid, image_path="", threshold=0.85, timeout_ms=5000)
    if action_type == ActionType.WAIT_TEXT:
        return Action(type=action_type, id=aid, query="Loading", timeout_ms=10000)
    if action_type == ActionType.WAIT_IMAGE:
        return Action(type=action_type, id=aid, image_path="", timeout_ms=10000)
    if action_type == ActionType.IF_TEXT:
        return Action(type=action_type, id=aid, query="Success", timeout_ms=5000)
    if action_type == ActionType.IF_IMAGE:
        return Action(type=action_type, id=aid, image_path="", threshold=0.85, timeout_ms=5000)
    if action_type in (ActionType.ELSE, ActionType.ENDIF):
        return Action(type=action_type, id=aid)
    return Action(type=action_type, id=aid)
