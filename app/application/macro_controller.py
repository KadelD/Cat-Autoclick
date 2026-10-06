"""Preset list, selection, dirty tracking, and workflow mutations (MCP-ready)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from PySide6.QtGui import QUndoStack

from app.application.step_factory import default_action

from app.application.workflow_ops import (

    apply_insert,

    apply_move,

    apply_remove_range,

    branch_insert_index,

    delete_span,

    duplicate_at,

    try_validate_control_flow,

)

from app.application.workflow_undo import (
    AddStepCommand,
    DuplicateStepCommand,
    MoveStepCommand,
    RemoveStepsCommand,
    UpdateStepCommand,
)

from app.core.control_flow import ControlFlowError

from app.core.models import Action, ActionType, Preset

from app.core.store import PresetStore

class MacroController(QObject):

    """Owns in-memory presets and coordinates save/load + workflow editing."""

    presets_changed = Signal()

    preset_selected = Signal(object)  # Preset | None

    macro_changed = Signal(object)  # Preset | None

    dirty_changed = Signal(bool)

    status_message = Signal(str)

    step_added = Signal(int)

    step_updated = Signal(int)

    step_removed = Signal(int)

    step_moved = Signal(int, int)

    selection_changed = Signal(object)  # int | None

    validation_changed = Signal(object)  # str | None error

    def __init__(self, store: PresetStore | None = None) -> None:

        super().__init__()

        self._store = store or PresetStore()

        self._store.ensure_default()

        self._presets: list[Preset] = self._store.list_presets()

        self._current: Preset | None = self._presets[0] if self._presets else None

        self._dirty_ids: set[str] = set()

        self._deleted_ids: set[str] = set()

        self._selected_step: int | None = None

        self._branch_kind: str | None = None

        self.undo_stack = QUndoStack(self)

    @property

    def presets(self) -> list[Preset]:

        return list(self._presets)

    @property

    def current(self) -> Preset | None:

        return self._current

    @property

    def is_dirty(self) -> bool:

        return bool(self._dirty_ids or self._deleted_ids)

    @property

    def selected_step_index(self) -> int | None:

        return self._selected_step

    @property

    def selected_branch_kind(self) -> str | None:

        return self._branch_kind

    def get_current_macro(self) -> Preset | None:

        """Return the active preset (alias for MCP/tools)."""

        return self._current

    def get_workflow(self) -> list[Action]:

        """Flat action list for the current preset."""

        if self._current is None:

            return []

        return list(self._current.actions)

    def select(self, preset_id: str | None) -> None:

        """Select preset by id; None clears selection."""

        if preset_id is None:

            self._current = None

            self._clear_selection()

            self.preset_selected.emit(None)

            self.macro_changed.emit(None)

            return

        for p in self._presets:

            if p.id == preset_id:

                self._current = p

                self._clear_selection()

                self.undo_stack.clear()

                self.preset_selected.emit(p)

                self.macro_changed.emit(p)

                self._emit_validation()

                return

    def select_index(self, index: int) -> None:

        """Select preset by list index."""

        if 0 <= index < len(self._presets):

            self._current = self._presets[index]

            self._clear_selection()

            self.undo_stack.clear()

            self.preset_selected.emit(self._current)

            self.macro_changed.emit(self._current)

            self._emit_validation()

    def select_step(self, step_index: int | None, *, branch_kind: str | None = None) -> None:

        """Update workflow selection for inspector and insert position."""

        self._selected_step = step_index

        self._branch_kind = branch_kind

        self.selection_changed.emit(step_index)

    def create_preset(self, name: str) -> Preset:

        """Add a new empty preset and select it."""

        preset = Preset(name=name.strip() or "Untitled")

        self._presets.append(preset)

        self._dirty_ids.add(preset.id)

        self._current = preset

        self._clear_selection()

        self.presets_changed.emit()

        self.preset_selected.emit(preset)

        self.macro_changed.emit(preset)

        self.dirty_changed.emit(True)

        return preset

    def rename_current(self, name: str) -> None:

        """Rename the selected preset."""

        if self._current is None:

            return

        self._current.name = name.strip() or self._current.name

        self._mark_dirty()

        self.presets_changed.emit()

    def delete_preset(self, preset_id: str) -> None:

        """Remove preset from list (save commits delete)."""

        self._presets = [p for p in self._presets if p.id != preset_id]

        if preset_id not in self._deleted_ids:

            disk_ids = {p.id for p in self._store.list_presets()}

            if preset_id in disk_ids:

                self._deleted_ids.add(preset_id)

        self._dirty_ids.discard(preset_id)

        if self._current and self._current.id == preset_id:

            self._current = self._presets[0] if self._presets else None

            self._clear_selection()

            self.preset_selected.emit(self._current)

            self.macro_changed.emit(self._current)

        self.presets_changed.emit()

        self.dirty_changed.emit(self.is_dirty)

    def validate_workflow(self) -> str | None:

        """Validate current macro control flow."""

        if self._current is None:

            return None

        return try_validate_control_flow(self._current.actions)

    def add_step(

        self,

        action: Action | ActionType,

        position: int | None = None,

        *,

        use_undo: bool = True,

    ) -> int | None:

        """Insert a step; returns flat index or None on failure."""

        if self._current is None:

            return None

        act = default_action(action) if isinstance(action, ActionType) else action

        if position is None:

            position = branch_insert_index(

                self._current.actions,

                self._selected_step,

                self._branch_kind,

            )

        try:

            if use_undo:

                self.undo_stack.push(AddStepCommand(self, act, position))

            else:

                self._set_actions(apply_insert(self._current.actions, position, act))

            self.step_added.emit(position)

            return position

        except ControlFlowError as exc:

            self.status_message.emit(str(exc))

            return None

    def update_action(self, index: int, action: Action, *, use_undo: bool = True) -> None:
        """Replace step at index (undoable by default)."""
        if self._current is None or not (0 <= index < len(self._current.actions)):
            return
        if use_undo:
            prev = self._current.actions[index]
            self.undo_stack.push(UpdateStepCommand(self, index, prev, action))
        else:
            self._current.actions[index] = action
            self._mark_dirty()
            self.macro_changed.emit(self._current)
            self.step_updated.emit(index)

    def update_step(self, index: int, action: Action, *, use_undo: bool = True) -> None:
        """MCP alias for update_action."""
        self.update_action(index, action, use_undo=use_undo)

    def delete_step(self, index: int, *, use_undo: bool = True) -> tuple[int, int] | None:

        """Delete step or whole if-block; returns removed span."""

        if self._current is None or not (0 <= index < len(self._current.actions)):

            return None

        start, end = delete_span(self._current.actions, index)

        try:

            if use_undo:

                self.undo_stack.push(RemoveStepsCommand(self, start, end))

            else:

                self._set_actions(apply_remove_range(self._current.actions, start, end))

            self.step_removed.emit(start)

            if self._selected_step is not None and start <= self._selected_step <= end:

                self.select_step(None)

            return start, end

        except ControlFlowError as exc:

            self.status_message.emit(str(exc))

            return None

    def duplicate_step(self, index: int, *, use_undo: bool = True) -> int | None:

        """Duplicate step or if-block; returns new copy start index."""

        if self._current is None or not (0 <= index < len(self._current.actions)):

            return None

        try:

            if use_undo:

                cmd = DuplicateStepCommand(self, index)

                self.undo_stack.push(cmd)

                return cmd.new_index

            new_list, new_idx = duplicate_at(self._current.actions, index)

            self._set_actions(new_list)

            return new_idx

        except ControlFlowError as exc:

            self.status_message.emit(str(exc))

            return None

    def move_step(self, source: int, target: int, *, use_undo: bool = True) -> bool:

        """Move step or if-block to flat target index."""

        if self._current is None:

            return False

        try:

            if use_undo:

                self.undo_stack.push(MoveStepCommand(self, source, target))

            else:

                self._set_actions(apply_move(self._current.actions, source, target))

            self.step_moved.emit(source, target)

            return True

        except ControlFlowError as exc:

            self.status_message.emit(str(exc))

            return False

    def update_actions(self, actions: list[Action]) -> None:

        """Replace actions on current preset (bulk)."""

        if self._current is None:

            return

        self._set_actions(actions)

    def append_action(self, action: Action) -> None:

        """Append one step (recording); skips undo stack."""

        if self._current is None:

            return

        self._current.actions.append(action)

        self._mark_dirty()

        idx = len(self._current.actions) - 1

        self.macro_changed.emit(self._current)

        self.step_added.emit(idx)

    def remove_action(self, index: int) -> None:

        """Delete step at index without undo (legacy)."""

        self.delete_step(index, use_undo=False)

    def move_action(self, source: int, target: int) -> None:

        """Reorder without undo (legacy)."""

        self.move_step(source, target, use_undo=False)

    def set_playback_options(

        self,

        *,

        loop_count: int | None = None,

        jitter_ms: int | None = None,

        monitor_index: int | None = None,

    ) -> None:

        """Update preset-level play settings from inspector toolbar."""

        if self._current is None:

            return

        if loop_count is not None:

            self._current.loop_count = loop_count

        if jitter_ms is not None:

            self._current.jitter_ms = max(0, jitter_ms)

        if monitor_index is not None:

            self._current.monitor_index = monitor_index

        self._mark_dirty()

    def save_all(self) -> None:

        """Persist all presets and clear dirty state."""

        err = self.validate_workflow()

        if err and self._current is not None:

            self.status_message.emit(f"Cannot save: {err}")

            return

        for preset_id in list(self._deleted_ids):

            self._store.delete(preset_id)

        self._deleted_ids.clear()

        for preset in self._presets:

            self._store.save(preset)

        self._dirty_ids.clear()

        self._presets = self._store.list_presets()

        cur_id = self._current.id if self._current else None

        if cur_id:

            self._current = next(

                (p for p in self._presets if p.id == cur_id),

                self._presets[0] if self._presets else None,

            )

        self.presets_changed.emit()

        self.preset_selected.emit(self._current)

        self.macro_changed.emit(self._current)

        self.dirty_changed.emit(False)

        self.status_message.emit("Saved")

    def reload_from_disk(self) -> None:

        """Refresh preset list from store."""

        self._presets = self._store.list_presets()

        self.presets_changed.emit()

    def _set_actions(self, actions: list[Action], *, emit_macro_changed: bool = True) -> None:

        """Internal: assign actions and mark dirty."""

        if self._current is None:

            return

        self._current.actions = actions

        self._mark_dirty()

        if emit_macro_changed:

            self.macro_changed.emit(self._current)

        self._emit_validation()

    def _mark_dirty(self) -> None:

        if self._current is not None:

            self._dirty_ids.add(self._current.id)

        self.dirty_changed.emit(True)

    def _clear_selection(self) -> None:

        self._selected_step = None

        self._branch_kind = None

        self.selection_changed.emit(None)

    def _emit_validation(self) -> None:

        self.validation_changed.emit(self.validate_workflow())

