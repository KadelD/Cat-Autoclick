"""Right-hand step inspector — compact properties panel."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.models import Action
from app.ui.inspector.step_inspector import StepInspectorForm
from app.ui.styles.icons import step_icon_for_action
from app.ui.styles.tokens import Colors, Control
from app.ui.widgets import AppButton


class InspectorPanel(QFrame):
    """Contextual step editor — form scrolls; Save/Delete stay pinned."""

    delete_requested = Signal(int)
    save_action = Signal(int, object)  # index, Action
    pick_region = Signal(int)  # step index

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)
        self.setStyleSheet(
            f"QFrame#panel {{ background: {Colors.PANEL}; border-left: 1px solid {Colors.BORDER}; }}"
        )
        self._step_index: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QWidget()
        head_l = QVBoxLayout(head)
        head_l.setContentsMargins(14, 14, 14, 10)
        head_l.setSpacing(4)

        title_row = QWidget()
        from PySide6.QtWidgets import QHBoxLayout

        tr = QHBoxLayout(title_row)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(8)
        self._icon = QLabel()
        self._icon.setFixedSize(18, 18)
        self._icon.hide()
        tr.addWidget(self._icon)
        self._head = QLabel("Inspector")
        self._head.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Colors.TEXT};")
        tr.addWidget(self._head, stretch=1)
        head_l.addWidget(title_row)

        self._sub = QLabel("Select a step to edit")
        self._sub.setWordWrap(True)
        self._sub.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        head_l.addWidget(self._sub)
        outer.addWidget(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        body = QWidget()
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(14, 0, 14, 12)
        body_l.setSpacing(8)

        self._form = StepInspectorForm()
        self._form.pick_region_requested.connect(self._on_pick_region)
        self._form.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        body_l.addWidget(self._form)
        body_l.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

        foot = QFrame()
        foot.setStyleSheet(
            f"QFrame {{ background: {Colors.PANEL}; border-top: 1px solid {Colors.BORDER}; }}"
        )
        foot_l = QVBoxLayout(foot)
        foot_l.setContentsMargins(12, 10, 12, 12)
        foot_l.setSpacing(8)

        self.btn_save = AppButton("Save changes", variant="primary")
        self.btn_save.clicked.connect(self._save)
        self.btn_save.hide()
        foot_l.addWidget(self.btn_save)

        self.btn_delete = AppButton("Delete Step", variant="danger")
        self.btn_delete.clicked.connect(self._delete)
        self.btn_delete.hide()
        foot_l.addWidget(self.btn_delete)

        outer.addWidget(foot)

    def show_action(self, index: int, action: Action) -> None:
        """Load step into the form."""
        self._step_index = index
        title = StepInspectorForm.title_for(action)
        self._head.setText(f"STEP {index + 1:02d}  ·  {title}")
        self._sub.setText("Edit fields, then Save")
        self._icon.setPixmap(step_icon_for_action(action, Control.ICON, Colors.TEXT_SECONDARY))
        self._icon.show()
        self._form.load_action(action)
        self.btn_save.show()
        self.btn_delete.show()

    def clear(self) -> None:
        self._step_index = None
        self._head.setText("Inspector")
        self._sub.setText("Select a step to edit")
        self._icon.hide()
        self._form.clear()
        self.btn_save.hide()
        self.btn_delete.hide()

    def apply_region(self, x: int, y: int, w: int, h: int) -> None:
        """Set capture region fields after picker."""
        self._form.set_region(x, y, w, h)

    def _save(self) -> None:
        if self._step_index is None:
            return
        result = self._form.collect_and_build()
        if result is None:
            return
        if isinstance(result, str):
            self._form.show_error(result)
            return
        self.save_action.emit(self._step_index, result)

    def _on_pick_region(self) -> None:
        if self._step_index is not None:
            self.pick_region.emit(self._step_index)

    def _delete(self) -> None:
        if self._step_index is not None:
            self.delete_requested.emit(self._step_index)
