"""OCR step dialog used while recording (F6/F7 flow)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.core.models import Action, ActionType, MouseButton, OnFail
from app.ui.styles.tokens import Colors

OcrCallback = Callable[[Action], None]

_TYPE_CHOICES = (
    ("Find text", ActionType.FIND_TEXT),
    ("Wait text", ActionType.WAIT_TEXT),
    ("If text", ActionType.IF_TEXT),
)


class OcrCaptureDialog(QDialog):
    """Configure an OCR step after full-screen or area capture."""

    def __init__(
        self,
        *,
        monitor_index: int,
        region_x: int = 0,
        region_y: int = 0,
        region_w: int = 0,
        region_h: int = 0,
        on_ok: OcrCallback | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("OCR step")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.resize(400, 420)
        self._on_ok = on_ok or (lambda _a: None)
        self._monitor_index = monitor_index
        self._region = (region_x, region_y, region_w, region_h)

        layout = QVBoxLayout(self)
        title = QLabel("OCR capture")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        scope = (
            f"Full monitor {monitor_index}"
            if region_w <= 0 or region_h <= 0
            else f"Region {region_x},{region_y} {region_w}x{region_h} (mon {monitor_index})"
        )
        scope_l = QLabel(scope)
        scope_l.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        layout.addWidget(scope_l)

        form = QFormLayout()
        self._type = QComboBox()
        for label, _ in _TYPE_CHOICES:
            self._type.addItem(label)
        self._type.currentTextChanged.connect(self._on_type_change)
        form.addRow("Type", self._type)

        self._query = QLineEdit()
        self._query.returnPressed.connect(self._ok)
        form.addRow("Text", self._query)

        self._timeout = QLineEdit("5000")
        form.addRow("Timeout ms", self._timeout)

        self._on_fail = QComboBox()
        self._on_fail.addItems(["stop", "continue"])
        self._fail_label = QLabel("On fail")
        form.addRow(self._fail_label, self._on_fail)

        self._button = QComboBox()
        self._button.addItems(["left", "right", "middle"])
        self._btn_label = QLabel("Click")
        form.addRow(self._btn_label, self._button)

        layout.addLayout(form)

        self._error = QLabel("")
        self._error.setStyleSheet(f"color: {Colors.ERROR};")
        layout.addWidget(self._error)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        add = QPushButton("Add step")
        add.setObjectName("primary")
        add.clicked.connect(self._ok)
        actions.addWidget(cancel)
        actions.addWidget(add)
        layout.addLayout(actions)

        self._on_type_change(self._type.currentText())
        self._query.setFocus()

    def _selected_type(self) -> ActionType:
        label = self._type.currentText()
        for name, atype in _TYPE_CHOICES:
            if name == label:
                return atype
        return ActionType.FIND_TEXT

    def _on_type_change(self, _value: str) -> None:
        """Toggle on-fail and click button fields by action kind."""
        atype = self._selected_type()
        show_fail = atype in (ActionType.FIND_TEXT, ActionType.WAIT_TEXT)
        show_btn = atype == ActionType.FIND_TEXT
        self._fail_label.setVisible(show_fail)
        self._on_fail.setVisible(show_fail)
        self._btn_label.setVisible(show_btn)
        self._button.setVisible(show_btn)

    def _ok(self) -> None:
        query = self._query.text().strip()
        if not query:
            self._error.setText("Text is required")
            return
        try:
            timeout = max(0, int(self._timeout.text().strip()))
        except ValueError:
            self._error.setText("Timeout must be a number")
            return
        atype = self._selected_type()
        rx, ry, rw, rh = self._region
        action = Action(
            type=atype,
            query=query,
            timeout_ms=timeout,
            on_fail=OnFail(self._on_fail.currentText()),
            button=MouseButton(self._button.currentText()) if atype == ActionType.FIND_TEXT else None,
            capture_monitor=self._monitor_index,
            region_x=rx,
            region_y=ry,
            region_w=rw,
            region_h=rh,
        )
        self._on_ok(action)
        self.accept()

    @staticmethod
    def run(
        *,
        monitor_index: int,
        region_x: int = 0,
        region_y: int = 0,
        region_w: int = 0,
        region_h: int = 0,
        on_ok: OcrCallback,
        parent=None,
    ) -> None:
        """Modal OCR capture dialog."""
        dlg = OcrCaptureDialog(
            monitor_index=monitor_index,
            region_x=region_x,
            region_y=region_y,
            region_w=region_w,
            region_h=region_h,
            on_ok=on_ok,
            parent=parent,
        )
        dlg.exec()
