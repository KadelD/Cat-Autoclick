"""Compact, colored display metadata for action list rows."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.models import Action, ActionType, ClickPhase, KeyPhase
from app.ui_ctk import theme as T


@dataclass(frozen=True)
class RowStyle:
    """How an action row should look in the list."""

    icon: str  # Google Material Icons name (e.g. "mouse")
    text: str
    accent: str
    compact: bool = False
    emphasize: bool = False
    detail: str | None = None  # shown via info hover, e.g. coordinates


def row_style(action: Action) -> RowStyle:
    """Return Material icon name, short label, accent, and compact flag for a row."""
    if action.type == ActionType.DELAY:
        if action.delay_min_ms is not None and action.delay_max_ms is not None:
            text = f"{action.delay_min_ms}-{action.delay_max_ms} ms"
        else:
            text = f"{action.delay_ms} ms"
        return RowStyle(icon="schedule", text=text, accent=T.MUTED, compact=True)

    if action.type == ActionType.KEY:
        key = action.key or "?"
        if action.key_phase == KeyPhase.DOWN:
            return RowStyle(icon="keyboard_arrow_down", text=key, accent=T.CYAN, emphasize=True)
        if action.key_phase == KeyPhase.UP:
            return RowStyle(icon="keyboard_arrow_up", text=key, accent="#A5B4FC", emphasize=True)
        return RowStyle(icon="keyboard", text=key, accent=T.CYAN, emphasize=True)

    if action.type == ActionType.HOTKEY:
        return RowStyle(
            icon="keyboard_command_key",
            text="+".join(action.keys),
            accent=T.PURPLE,
            emphasize=True,
        )

    if action.type == ActionType.HOLD:
        target = action.key or f"mouse {(action.button.value if action.button else 'left')}"
        return RowStyle(
            icon="pause",
            text=target,
            accent=T.PURPLE,
            emphasize=True,
            detail=f"Hold {action.hold_ms} ms",
        )

    if action.type == ActionType.MOUSE_CLICK:
        btn = (action.button.value if action.button else "left")[0].upper()
        detail = f"Position ({action.x}, {action.y})"
        if action.click_count > 1:
            detail = f"Double-click · {detail}" if action.click_count == 2 else f"x{action.click_count} · {detail}"
        if action.click_phase == ClickPhase.DOWN:
            return RowStyle(
                icon="arrow_downward", text=btn, accent="#F472B6", emphasize=True, detail=detail
            )
        if action.click_phase == ClickPhase.UP:
            return RowStyle(
                icon="arrow_upward", text=btn, accent="#F9A8D4", emphasize=True, detail=detail
            )
        label = f"{btn}×{action.click_count}" if action.click_count > 1 else btn
        return RowStyle(
            icon="ads_click", text=label, accent="#F472B6", emphasize=True, detail=detail
        )

    if action.type == ActionType.MOUSE_MOVE:
        return RowStyle(
            icon="open_with",
            text="Move",
            accent="#FBBF24",
            detail=f"Position ({action.x}, {action.y})",
        )

    if action.type == ActionType.MOUSE_DRAG:
        btn = (action.button.value if action.button else "left")[0].upper()
        return RowStyle(
            icon="pan_tool",
            text=f"Drag {btn}",
            accent="#FBBF24",
            emphasize=True,
            detail=(
                f"({action.x}, {action.y}) → ({action.end_x}, {action.end_y}) "
                f"· {action.hold_ms} ms constant"
            ),
        )

    if action.type == ActionType.FIND_TEXT:
        return RowStyle(icon="find_in_page", text=f'Find "{action.query}"', accent=T.CYAN)
    if action.type == ActionType.FIND_IMAGE:
        return RowStyle(icon="image_search", text=f"Find {action.image_path}", accent="#34D399")
    if action.type == ActionType.WAIT_TEXT:
        return RowStyle(
            icon="hourglass_empty", text=f'Wait "{action.query}"', accent=T.MUTED, compact=True
        )
    if action.type == ActionType.WAIT_IMAGE:
        return RowStyle(
            icon="hourglass_empty", text=f"Wait {action.image_path}", accent=T.MUTED, compact=True
        )
    if action.type == ActionType.IF_TEXT:
        return RowStyle(icon="call_split", text=f'If "{action.query}"', accent=T.PURPLE)
    if action.type == ActionType.IF_IMAGE:
        return RowStyle(icon="call_split", text=f"If {action.image_path}", accent=T.PURPLE)
    if action.type == ActionType.ELSE:
        return RowStyle(
            icon="subdirectory_arrow_right", text="Else", accent=T.MUTED, compact=True
        )
    if action.type == ActionType.ENDIF:
        return RowStyle(icon="check_box", text="End if", accent=T.MUTED, compact=True)

    return RowStyle(icon="more_vert", text=action.summary(), accent=T.WHITE)
