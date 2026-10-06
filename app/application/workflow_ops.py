"""Flat-list workflow mutations with control-flow validation."""

from __future__ import annotations

from copy import deepcopy

from app.core.control_flow import ControlFlowError, find_if_block, validate_control_flow
from app.core.models import Action, ActionType

IF_TYPES = {ActionType.IF_TEXT, ActionType.IF_IMAGE}
MARKER_ALONE = {ActionType.ELSE, ActionType.ENDIF}


def try_validate_control_flow(actions: list[Action]) -> str | None:
    """Return error message if control flow is invalid."""
    try:
        validate_control_flow(actions)
    except ControlFlowError as exc:
        return str(exc)
    return None


def move_span(actions: list[Action], index: int) -> tuple[int, int]:
    """Inclusive index range moved together (whole if block when index is If)."""
    if not (0 <= index < len(actions)):
        raise IndexError(index)
    action = actions[index]
    if action.type in IF_TYPES:
        block = find_if_block(actions, index)
        return index, block.endif_index
    if action.type in MARKER_ALONE:
        raise ControlFlowError("Else and End If must move with their If block")
    return index, index


def if_block_span(actions: list[Action], if_index: int) -> tuple[int, int]:
    """Inclusive range for an if block from If through End If."""
    block = find_if_block(actions, if_index)
    return if_index, block.endif_index


def delete_span(actions: list[Action], index: int) -> tuple[int, int]:
    """Inclusive range removed when deleting index (whole block if If)."""
    action = actions[index]
    if action.type in IF_TYPES:
        return if_block_span(actions, index)
    return index, index


def insert_index_after(
    actions: list[Action],
    selected_index: int | None,
    *,
    inside_if: bool = False,
) -> int:
    """Flat insert position: after selection, or end of list."""
    if not actions or selected_index is None:
        return len(actions)
    if not (0 <= selected_index < len(actions)):
        return len(actions)
    if inside_if and actions[selected_index].type in IF_TYPES:
        return selected_index + 1
    start, end = delete_span(actions, selected_index) if actions[selected_index].type in IF_TYPES else (selected_index, selected_index)
    if actions[selected_index].type in IF_TYPES and not inside_if:
        return end + 1
    return selected_index + 1


def branch_insert_index(actions: list[Action], selected_index: int | None, branch_kind: str | None) -> int:
    """Insert index for palette: respect then/else branch selection."""
    if selected_index is None or not actions:
        return len(actions)
    if not (0 <= selected_index < len(actions)):
        return len(actions)
    action = actions[selected_index]
    if branch_kind == "then" and action.type in IF_TYPES:
        return selected_index + 1
    if branch_kind == "else":
        if action.type == ActionType.ELSE:
            return selected_index + 1
        if action.type in IF_TYPES:
            block = find_if_block(actions, selected_index)
            if block.else_index is not None:
                return block.else_index + 1
            return block.endif_index
    if action.type == ActionType.ELSE:
        return selected_index + 1
    if action.type in IF_TYPES:
        block = find_if_block(actions, selected_index)
        if block.else_index is not None and branch_kind == "else":
            return block.else_index + 1
        return selected_index + 1
    return selected_index + 1


def apply_move(actions: list[Action], source: int, target: int) -> list[Action]:
    """Move step or if-block to flat target index; raises ControlFlowError on invalid result."""
    if source == target or not actions:
        return list(actions)
    start, end = move_span(actions, source)
    chunk = actions[start : end + 1]
    tail = actions[:start] + actions[end + 1 :]
    if target > end:
        target -= len(chunk)
    elif target > start:
        target = start
    target = max(0, min(target, len(tail)))
    result = tail[:target] + chunk + tail[target:]
    validate_control_flow(result)
    return result


def apply_insert(actions: list[Action], index: int, action: Action) -> list[Action]:
    """Insert one action at index and validate."""
    index = max(0, min(index, len(actions)))
    result = actions[:index] + [action] + actions[index:]
    validate_control_flow(result)
    return result


def apply_remove_range(actions: list[Action], start: int, end: int) -> list[Action]:
    """Remove inclusive range and validate."""
    result = actions[:start] + actions[end + 1 :]
    validate_control_flow(result)
    return result


def duplicate_at(actions: list[Action], index: int) -> tuple[list[Action], int]:
    """Duplicate one step or whole if-block; returns (new_list, new_copy_start_index)."""
    from app.application.step_factory import new_action_id

    start, end = move_span(actions, index)
    copies = [deepcopy(a) for a in actions[start : end + 1]]
    for a in copies:
        a.id = new_action_id()
    insert_at = end + 1
    result = actions[:insert_at] + copies + actions[insert_at:]
    validate_control_flow(result)
    return result, insert_at
