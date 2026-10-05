"""Resolve if/else/endif marker pairs in a flat action list."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.models import Action, ActionType

IF_TYPES = {ActionType.IF_TEXT, ActionType.IF_IMAGE}


@dataclass(frozen=True)
class IfBlock:
    """Indices for one if/else/endif block."""

    if_index: int
    else_index: int | None
    endif_index: int


class ControlFlowError(ValueError):
    """Raised when if/else/endif markers are unbalanced."""


def find_if_block(actions: list[Action], if_index: int) -> IfBlock:
    """Find matching else/endif for the if marker at if_index (supports nesting)."""
    if if_index < 0 or if_index >= len(actions):
        raise ControlFlowError(f"if_index out of range: {if_index}")
    if actions[if_index].type not in IF_TYPES:
        raise ControlFlowError(f"Action at {if_index} is not an if marker")

    depth = 0
    else_index: int | None = None
    for i in range(if_index + 1, len(actions)):
        kind = actions[i].type
        if kind in IF_TYPES:
            depth += 1
            continue
        if kind == ActionType.ELSE:
            if depth == 0:
                if else_index is not None:
                    raise ControlFlowError(f"Duplicate else for if at {if_index}")
                else_index = i
            continue
        if kind == ActionType.ENDIF:
            if depth == 0:
                return IfBlock(if_index=if_index, else_index=else_index, endif_index=i)
            depth -= 1

    raise ControlFlowError(f"Missing endif for if at {if_index}")


def validate_control_flow(actions: list[Action]) -> None:
    """Validate all if/else/endif markers in the list."""
    stack: list[int] = []
    for i, action in enumerate(actions):
        if action.type in IF_TYPES:
            stack.append(i)
            continue
        if action.type == ActionType.ELSE:
            if not stack:
                raise ControlFlowError(f"else without if at {i}")
            continue
        if action.type == ActionType.ENDIF:
            if not stack:
                raise ControlFlowError(f"endif without if at {i}")
            stack.pop()
    if stack:
        raise ControlFlowError(f"Unclosed if at {stack[-1]}")


def next_index_after_if(actions: list[Action], if_index: int, condition_true: bool) -> int:
    """
    Return the index of the first action to run inside the chosen branch.

    Caller should treat endif as a no-op jump target (run from returned index,
    and when hitting else while in then-branch, jump to endif+1).
    """
    block = find_if_block(actions, if_index)
    if condition_true:
        return if_index + 1
    if block.else_index is not None:
        return block.else_index + 1
    return block.endif_index + 1
