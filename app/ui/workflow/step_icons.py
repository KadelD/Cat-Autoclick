"""Icon helpers for workflow rows — vector pixmaps (no emoji)."""

from __future__ import annotations

from PySide6.QtGui import QPixmap

from app.core.models import Action, ActionType
from app.ui.styles.icons import step_icon_for_action, step_icon_for_type, step_icon_key
from app.ui.styles.tokens import Colors, Control


def icon_key_for_type(action_type: ActionType) -> str:
    """Registry key for an action type."""
    return step_icon_key(action_type)


def icon_pixmap_for_type(
    action_type: ActionType,
    size: int = Control.ICON,
    color: str = Colors.TEXT,
) -> QPixmap:
    """Vector pixmap for palette / workflow."""
    return step_icon_for_type(action_type, size, color)


def icon_pixmap_for_action(
    action: Action,
    size: int = Control.ICON,
    color: str = Colors.TEXT,
) -> QPixmap:
    """Vector pixmap for a concrete action."""
    return step_icon_for_action(action, size, color)


# Back-compat names used by older imports (return empty — prefer pixmap APIs).
def icon_char_for_type(action_type: ActionType) -> str:
    """Deprecated: emoji removed; returns empty string."""
    return ""


def icon_char_for_action(action: Action) -> str:
    """Deprecated: emoji removed; returns empty string."""
    return ""
