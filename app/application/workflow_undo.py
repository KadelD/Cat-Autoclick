"""QUndoCommand wrappers for macro workflow edits."""

from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from app.application.workflow_ops import apply_insert, apply_move, apply_remove_range, duplicate_at
from app.core.models import Action


class _MacroEditCommand(QUndoCommand):
    """Base command that snapshots actions before/after."""

    def __init__(self, controller, text: str) -> None:
        super().__init__(text)
        self._macro = controller
        self._before: list[Action] | None = None
        self._after: list[Action] | None = None

    def _snapshot_before(self) -> None:
        preset = self._macro.current
        self._before = list(preset.actions) if preset else []

    def _apply_after(self) -> None:
        if self._after is not None:
            self._macro._set_actions(self._after, emit_macro_changed=True)


class AddStepCommand(_MacroEditCommand):
    """Insert a step at a flat index."""

    def __init__(self, controller, action: Action, index: int) -> None:
        super().__init__(controller, "Add step")
        self._action = action
        self._index = index

    def redo(self) -> None:  # noqa: D102
        if self._before is None:
            self._snapshot_before()
        preset = self._macro.current
        if preset is None:
            return
        self._after = apply_insert(preset.actions, self._index, self._action)
        self._apply_after()

    def undo(self) -> None:  # noqa: D102
        if self._before is not None:
            self._macro._set_actions(self._before, emit_macro_changed=True)


class RemoveStepsCommand(_MacroEditCommand):
    """Remove an inclusive flat index range."""

    def __init__(self, controller, start: int, end: int) -> None:
        super().__init__(controller, "Delete step")
        self._start = start
        self._end = end

    def redo(self) -> None:  # noqa: D102
        if self._before is None:
            self._snapshot_before()
        preset = self._macro.current
        if preset is None:
            return
        self._after = apply_remove_range(preset.actions, self._start, self._end)
        self._apply_after()

    def undo(self) -> None:  # noqa: D102
        if self._before is not None:
            self._macro._set_actions(self._before, emit_macro_changed=True)


class MoveStepCommand(_MacroEditCommand):
    """Move a step or if-block."""

    def __init__(self, controller, source: int, target: int) -> None:
        super().__init__(controller, "Move step")
        self._source = source
        self._target = target

    def redo(self) -> None:  # noqa: D102
        if self._before is None:
            self._snapshot_before()
        preset = self._macro.current
        if preset is None:
            return
        self._after = apply_move(preset.actions, self._source, self._target)
        self._apply_after()

    def undo(self) -> None:  # noqa: D102
        if self._before is not None:
            self._macro._set_actions(self._before, emit_macro_changed=True)


class UpdateStepCommand(_MacroEditCommand):
    """Replace one step at index."""

    def __init__(self, controller, index: int, prev: Action, new: Action) -> None:
        super().__init__(controller, "Edit step")
        self._index = index
        self._prev = prev
        self._new = new

    def redo(self) -> None:  # noqa: D102
        preset = self._macro.current
        if preset is None or not (0 <= self._index < len(preset.actions)):
            return
        acts = list(preset.actions)
        acts[self._index] = self._new
        self._macro._set_actions(acts, emit_macro_changed=True)
        self._macro.step_updated.emit(self._index)

    def undo(self) -> None:  # noqa: D102
        preset = self._macro.current
        if preset is None or not (0 <= self._index < len(preset.actions)):
            return
        acts = list(preset.actions)
        acts[self._index] = self._prev
        self._macro._set_actions(acts, emit_macro_changed=True)
        self._macro.step_updated.emit(self._index)


class DuplicateStepCommand(_MacroEditCommand):
    """Duplicate step or if-block."""

    def __init__(self, controller, index: int) -> None:
        super().__init__(controller, "Duplicate step")
        self._index = index
        self._new_index = index

    @property
    def new_index(self) -> int:
        """Flat index of the duplicated copy after redo."""
        return self._new_index

    def redo(self) -> None:  # noqa: D102
        if self._before is None:
            self._snapshot_before()
        preset = self._macro.current
        if preset is None:
            return
        self._after, self._new_index = duplicate_at(preset.actions, self._index)
        self._apply_after()

    def undo(self) -> None:  # noqa: D102
        if self._before is not None:
            self._macro._set_actions(self._before, emit_macro_changed=True)
