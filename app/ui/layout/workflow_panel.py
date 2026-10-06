"""Center workflow tree, toolbar, empty state, and keyboard shortcuts."""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.application.macro_controller import MacroController
from app.application.workflow_ops import if_block_span
from app.core.models import ActionType
from app.core.monitors import list_monitors
from app.core.settings import get_settings
from app.ui.dialogs.add_step_palette import AddStepPaletteDialog
from app.ui.styles.icons import icon
from app.ui.styles.tokens import Colors
from app.ui.widgets import AppButton
from app.ui.workflow.workflow_delegate import WorkflowItemDelegate
from app.ui.workflow.workflow_model import WorkflowRoles, WorkflowTreeModel
from app.ui.workflow.workflow_view import WorkflowTreeView


class WorkflowPanel(QFrame):
    """Workflow editor tree + loop/jitter/monitor row."""

    step_selected = Signal(int)
    add_step_requested = Signal()
    save_requested = Signal()
    record_requested = Signal()

    def __init__(self, macros: MacroController) -> None:
        super().__init__()
        self._macros = macros
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.title = QLabel("Workflow")
        self.title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {Colors.TEXT};")
        header.addWidget(self.title)
        header.addStretch()
        self.btn_add = AppButton("Add Step", variant="primary")
        self.btn_add.setIcon(icon("add", 14, "#FFFFFF"))
        self.btn_add.clicked.connect(self._open_add_palette)
        header.addWidget(self.btn_add)
        self.btn_record = AppButton("Record", variant="ghost")
        self.btn_record.setIcon(icon("record", 14, Colors.RECORD))
        self.btn_record.clicked.connect(self.record_requested.emit)
        header.addWidget(self.btn_record)
        self.btn_save = AppButton("Save", variant="ghost")
        self.btn_save.setIcon(icon("save", 14, Colors.TEXT_SECONDARY))
        self.btn_save.clicked.connect(self.save_requested.emit)
        header.addWidget(self.btn_save)
        layout.addLayout(header)

        opts = QHBoxLayout()
        opts.setSpacing(8)
        for label_text, attr, width in (
            ("Monitor", "monitor", 220),
            ("Loops", "loops", 70),
            ("Jitter ms", "jitter", 80),
        ):
            lab = QLabel(label_text)
            lab.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
            opts.addWidget(lab)
            if attr == "monitor":
                self.monitor = QComboBox()
                for m in list_monitors():
                    self.monitor.addItem(m.label, m.index)
                self.monitor.setFixedWidth(width)
                self.monitor.currentIndexChanged.connect(self._sync_options)
                opts.addWidget(self.monitor)
            elif attr == "loops":
                self.loops = QSpinBox()
                self.loops.setRange(0, 99999)
                self.loops.setFixedWidth(width)
                self.loops.setToolTip("0 = infinite")
                self.loops.valueChanged.connect(self._sync_options)
                opts.addWidget(self.loops)
            else:
                self.jitter = QSpinBox()
                self.jitter.setRange(0, 60000)
                self.jitter.setFixedWidth(width)
                self.jitter.valueChanged.connect(self._sync_options)
                opts.addWidget(self.jitter)
        opts.addStretch()
        layout.addLayout(opts)

        self._stack = QStackedWidget()
        self._empty = QWidget()
        empty_l = QVBoxLayout(self._empty)
        empty_l.addStretch()
        empty_title = QLabel("No steps yet")
        empty_title.setAlignment(Qt.AlignCenter)
        empty_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {Colors.TEXT};")
        empty_sub = QLabel("Add your first automation step to begin.")
        empty_sub.setAlignment(Qt.AlignCenter)
        empty_sub.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px;")
        empty_l.addWidget(empty_title)
        empty_l.addWidget(empty_sub)
        empty_btns = QHBoxLayout()
        empty_btns.addStretch()
        b1 = AppButton("Add Step", variant="primary")
        b1.setIcon(icon("add", 14, "#FFFFFF"))
        b1.clicked.connect(self._open_add_palette)
        b2 = AppButton("Record", variant="secondary")
        b2.setIcon(icon("record", 14, Colors.RECORD))
        b2.clicked.connect(self.record_requested.emit)
        empty_btns.addWidget(b1)
        empty_btns.addWidget(b2)
        empty_btns.addStretch()
        empty_l.addLayout(empty_btns)
        empty_l.addStretch()
        self._stack.addWidget(self._empty)

        tree_host = QWidget()
        tree_l = QVBoxLayout(tree_host)
        tree_l.setContentsMargins(0, 0, 0, 0)
        self.model = WorkflowTreeModel()
        self.tree = WorkflowTreeView(self.model)
        self.tree.setItemDelegate(WorkflowItemDelegate(self.tree))
        self.tree.move_requested.connect(self._on_move)
        self.tree.selectionModel().selectionChanged.connect(self._on_select)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        tree_l.addWidget(self.tree)
        self._stack.addWidget(tree_host)
        layout.addWidget(self._stack, stretch=1)

        self._loading = QLabel("")
        self._loading.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._loading)

        hint = QLabel("Drag to reorder  ·  Alt+Up/Down to move  ·  Delete  ·  Ctrl+D duplicate")
        hint.setObjectName("hint")
        layout.addWidget(hint)

        self._wire_shortcuts()
        # Avoid double-refresh: main_window also listens to macro_changed for load_preset
        macros.selection_changed.connect(self._restore_selection)
        macros.step_added.connect(self._on_step_added)

    def _wire_shortcuts(self) -> None:
        """Keyboard editing shortcuts on the workflow tree."""
        QShortcut(QKeySequence(Qt.Key_Delete), self.tree, self._delete_selected)
        QShortcut(QKeySequence("Ctrl+D"), self.tree, self._duplicate_selected)
        QShortcut(QKeySequence("Alt+Up"), self.tree, lambda: self._nudge(-1))
        QShortcut(QKeySequence("Alt+Down"), self.tree, lambda: self._nudge(1))
        # Only when the tree itself has focus — avoid stealing keys app-wide.
        up = QShortcut(QKeySequence(Qt.Key_Up), self.tree)
        up.setContext(Qt.WidgetShortcut)
        up.activated.connect(lambda: self._nav_step(-1))
        down = QShortcut(QKeySequence(Qt.Key_Down), self.tree)
        down.setContext(Qt.WidgetShortcut)
        down.activated.connect(lambda: self._nav_step(1))
        undo = QAction("Undo", self.tree)
        undo.setShortcut(QKeySequence.Undo)
        undo.triggered.connect(self._macros.undo_stack.undo)
        self.tree.addAction(undo)
        redo = QAction("Redo", self.tree)
        redo.setShortcut(QKeySequence.Redo)
        redo.triggered.connect(self._macros.undo_stack.redo)
        self.tree.addAction(redo)

    def load_preset(self) -> None:
        """Refresh tree from current macro (deferred for large presets)."""
        preset = self._macros.current
        if preset is None:
            self.model.set_preset(None)
            self._stack.setCurrentIndex(0)
            return
        self.title.setText(preset.name)
        self.loops.blockSignals(True)
        self.jitter.blockSignals(True)
        self.loops.setValue(preset.loop_count)
        self.jitter.setValue(preset.jitter_ms)
        idx = preset.monitor_index
        for i in range(self.monitor.count()):
            if self.monitor.itemData(i) == idx:
                self.monitor.setCurrentIndex(i)
                break
        self.loops.blockSignals(False)
        self.jitter.blockSignals(False)

        if len(preset.actions) == 0:
            self.model.set_preset(preset)
            self._stack.setCurrentIndex(0)
            return

        if len(preset.actions) > 80:
            self._loading.setText("Loading workflow…")
            QTimer.singleShot(0, lambda: self._finish_load(preset))
        else:
            self._finish_load(preset)

    def _finish_load(self, preset) -> None:
        """Apply model reset and expand tree."""
        self.model.set_preset(preset)
        self._loading.setText("")
        self._stack.setCurrentIndex(1)
        self.tree.expand_all()
        self._restore_selection(self._macros.selected_step_index)

    def set_execution_step(self, step_index: int | None) -> None:
        """Highlight the step reported by playback (hook)."""
        self.model.set_execution_index(step_index)

    def _sync_options(self) -> None:
        if self._macros.current is None:
            return
        mon = self.monitor.currentData()
        self._macros.set_playback_options(
            loop_count=self.loops.value(),
            jitter_ms=self.jitter.value(),
            monitor_index=int(mon) if mon is not None else 0,
        )

    def _on_select(self) -> None:
        indexes = self.tree.selectionModel().selectedIndexes()
        if not indexes:
            return
        idx = indexes[0]
        step = self.model.step_index_at(idx)
        branch = idx.data(WorkflowRoles.BranchKind)
        self._macros.select_step(step, branch_kind=branch if isinstance(branch, str) else None)
        if step is not None:
            self.step_selected.emit(step)

    def _on_step_added(self, index: int) -> None:
        """Select newly inserted step after model refresh."""
        self._macros.select_step(index)
        self.step_selected.emit(index)

    def _restore_selection(self, step_index: object) -> None:
        if step_index is None or not isinstance(step_index, int):
            return
        midx = self.model.index_for_step(step_index)
        if not midx.isValid():
            return
        sm = self.tree.selectionModel()
        sm.blockSignals(True)
        flags = QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
        sm.setCurrentIndex(midx, flags)
        sm.blockSignals(False)
        self.tree.scrollTo(midx)

    def _open_add_palette(self) -> None:
        at = AddStepPaletteDialog.pick(self, ocr_enabled=get_settings().ocr_enabled)
        if at is None:
            return
        self._macros.add_step(at)

    def _delete_selected(self) -> None:
        step = self._macros.selected_step_index
        if step is None or self._macros.current is None:
            return
        actions = self._macros.current.actions
        if actions[step].type in (ActionType.IF_TEXT, ActionType.IF_IMAGE):
            span = if_block_span(actions, step)
            count = span[1] - span[0] + 1
            box = QMessageBox(self)
            box.setWindowTitle("Delete condition")
            box.setText(f"Delete this If block and all {count} steps inside it?")
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            if box.exec() != QMessageBox.Yes:
                return
        self._macros.delete_step(step)

    def _duplicate_selected(self) -> None:
        step = self._macros.selected_step_index
        if step is None:
            return
        new_idx = self._macros.duplicate_step(step)
        if new_idx is not None:
            self._macros.select_step(new_idx)

    def _nav_step(self, delta: int) -> None:
        """Move selection to previous/next flat step."""
        acts = self._macros.get_workflow()
        if not acts:
            return
        cur = self._macros.selected_step_index
        if cur is None:
            cur = 0
        else:
            cur = max(0, min(cur + delta, len(acts) - 1))
        self._macros.select_step(cur)
        midx = self.model.index_for_step(cur)
        if midx.isValid():
            self.tree.setCurrentIndex(midx)
        self.step_selected.emit(cur)

    def _nudge(self, delta: int) -> None:
        step = self._macros.selected_step_index
        if step is None:
            return
        target = step + delta if delta < 0 else step + 1
        if target < 0:
            return
        self._macros.move_step(step, target)

    def _on_move(self, source: int, target: int) -> None:
        if source == target:
            return
        self._macros.move_step(source, target)

    def _context_menu(self, pos) -> None:
        idx = self.tree.indexAt(pos)
        if not idx.isValid():
            return
        step = self.model.step_index_at(idx)
        branch = idx.data(WorkflowRoles.BranchKind)
        if step is not None:
            self._macros.select_step(step, branch_kind=branch if isinstance(branch, str) else None)
            self.step_selected.emit(step)

        menu = QMenu(self)
        menu.addAction("Add Step After", self._open_add_palette)
        if step is not None:
            menu.addAction("Duplicate", self._duplicate_selected)
            menu.addAction("Delete", self._delete_selected)
            menu.addSeparator()
            menu.addAction("Move Up", lambda: self._nudge(-1))
            menu.addAction("Move Down", lambda: self._nudge(1))
        if branch == "if" or (step is not None and self._macros.current and self._macros.current.actions[step].type in (ActionType.IF_TEXT, ActionType.IF_IMAGE)):
            menu.addSeparator()
            menu.addAction("Add Step Inside (Then)", lambda: self._add_inside("then"))
        if branch == "else" or branch == "if":
            menu.addAction("Add Step Inside (Else)", lambda: self._add_inside("else"))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _add_inside(self, branch: str) -> None:
        step = self._macros.selected_step_index
        self._macros.select_step(step, branch_kind=branch)
        self._open_add_palette()
