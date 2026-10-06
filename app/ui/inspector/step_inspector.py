"""Type-aware form for editing a single workflow step."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.application.action_form import (
    BUTTON_LABELS,
    ON_FAIL_LABELS,
    PHASE_CLICK,
    PHASE_KEY,
    VISION_TYPES,
    action_to_form,
    build_action_from_form,
)
from app.application.step_format import format_step_title
from app.core.models import Action, ActionType
from app.core.vision import templates_dir
from app.ui.styles.tokens import Colors


class _FieldRow(QWidget):
    """One labeled field row that can be shown/hidden as a unit."""

    def __init__(self, label: str, editor: QWidget) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        lab = QLabel(label)
        lab.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; font-weight: 600;")
        layout.addWidget(lab)
        layout.addWidget(editor)
        self.editor = editor


class StepInspectorForm(QWidget):
    """Editable fields for the selected action — only relevant rows visible."""

    save_requested = Signal(object)  # Action
    pick_region_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._action: Action | None = None
        self._fields: dict[str, QLineEdit | QComboBox] = {}
        self._rows: dict[str, _FieldRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self._fields_host = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_host)
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        self._fields_layout.setSpacing(10)
        root.addWidget(self._fields_host)

        self._btn_region = QPushButton("Pick region on screen…")
        self._btn_region.setObjectName("ghost")
        self._btn_region.setFixedHeight(30)
        self._btn_region.clicked.connect(self.pick_region_requested.emit)
        self._btn_region.hide()
        root.addWidget(self._btn_region)

        self._err = QLabel("")
        self._err.setWordWrap(True)
        self._err.setStyleSheet(f"color: {Colors.ERROR}; font-size: 12px;")
        self._err.hide()
        root.addWidget(self._err)

        root.addStretch(1)

        self._build_fields()
        self._set_all_hidden()

    def _add_row(self, key: str, label: str, editor: QLineEdit | QComboBox) -> None:
        """Register a field row."""
        row = _FieldRow(label, editor)
        self._fields[key] = editor
        self._rows[key] = row
        self._fields_layout.addWidget(row)

    def _build_fields(self) -> None:
        """Create all possible editors once."""
        self._x = QLineEdit("100")
        self._y = QLineEdit("100")
        self._add_row("x", "X", self._x)
        self._add_row("y", "Y", self._y)

        self._end_x = QLineEdit("200")
        self._end_y = QLineEdit("200")
        self._add_row("end_x", "End X", self._end_x)
        self._add_row("end_y", "End Y", self._end_y)

        self._button = QComboBox()
        self._button.addItems(list(BUTTON_LABELS.keys()))
        self._add_row("button", "Button", self._button)

        self._key = QLineEdit()
        self._key.setPlaceholderText("a / ctrl / f5")
        self._add_row("key", "Key", self._key)

        self._keys = QLineEdit()
        self._keys.setPlaceholderText("ctrl+c")
        self._add_row("keys", "Hotkey", self._keys)

        self._hold_ms = QLineEdit("500")
        self._add_row("hold_ms", "Hold ms", self._hold_ms)

        self._delay_ms = QLineEdit("500")
        self._add_row("delay_ms", "Delay ms", self._delay_ms)

        self._phase_click = QComboBox()
        self._phase_click.addItems(list(PHASE_CLICK.keys()))
        self._add_row("phase_click", "Click phase", self._phase_click)

        self._phase_key = QComboBox()
        self._phase_key.addItems(list(PHASE_KEY.keys()))
        self._add_row("phase_key", "Key phase", self._phase_key)

        self._query = QLineEdit()
        self._query.setPlaceholderText("Text to find")
        self._add_row("query", "Condition / Text", self._query)

        img_host = QWidget()
        img_l = QHBoxLayout(img_host)
        img_l.setContentsMargins(0, 0, 0, 0)
        img_l.setSpacing(6)
        self._image_path = QLineEdit()
        self._image_path.setPlaceholderText("template.png")
        btn_browse = QPushButton("Browse")
        btn_browse.setObjectName("ghost")
        btn_browse.setFixedHeight(30)
        btn_browse.setFixedWidth(72)
        btn_browse.clicked.connect(self._browse_image)
        img_l.addWidget(self._image_path, stretch=1)
        img_l.addWidget(btn_browse)
        # Wrap as a row with custom editor widget
        row = _FieldRow("Image", img_host)
        self._fields["image_path"] = self._image_path
        self._rows["image_path"] = row
        self._fields_layout.addWidget(row)

        self._threshold = QLineEdit("0.85")
        self._add_row("threshold", "Threshold", self._threshold)

        self._timeout_ms = QLineEdit("5000")
        self._add_row("timeout_ms", "Timeout ms", self._timeout_ms)

        self._on_fail = QComboBox()
        self._on_fail.addItems(list(ON_FAIL_LABELS.keys()))
        self._add_row("on_fail", "On fail", self._on_fail)

        self._region_x = QLineEdit("0")
        self._region_y = QLineEdit("0")
        self._region_w = QLineEdit("0")
        self._region_h = QLineEdit("0")
        self._add_row("region_x", "Region X", self._region_x)
        self._add_row("region_y", "Region Y", self._region_y)
        self._add_row("region_w", "Region W", self._region_w)
        self._add_row("region_h", "Region H", self._region_h)

        self._capture_monitor = QLineEdit()
        self._capture_monitor.setPlaceholderText("empty = use preset monitor")
        self._add_row("capture_monitor", "Capture monitor", self._capture_monitor)

    def load_action(self, action: Action) -> None:
        """Populate fields from action and show only relevant rows."""
        self._action = action
        data = action_to_form(action)
        for key, widget in self._fields.items():
            val = data.get(key, "")
            if isinstance(widget, QComboBox):
                idx = widget.findText(val)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            else:
                widget.setText(val)
        self._sync_visibility(action.type)
        self._err.hide()

    def clear(self) -> None:
        """Reset inspector."""
        self._action = None
        self._set_all_hidden()
        self._err.hide()

    def set_region(self, x: int, y: int, w: int, h: int) -> None:
        """Apply region picker result."""
        self._region_x.setText(str(x))
        self._region_y.setText(str(y))
        self._region_w.setText(str(w))
        self._region_h.setText(str(h))

    def collect_and_build(self) -> Action | str | None:
        """Build updated Action from form, or error string / None if empty."""
        if self._action is None:
            return None
        result = build_action_from_form(self._action, self._field_values(), self._action.type)
        return result

    def show_error(self, message: str) -> None:
        """Show validation error under the form."""
        self._err.setText(message)
        self._err.show()

    def _field_values(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, widget in self._fields.items():
            if isinstance(widget, QComboBox):
                out[key] = widget.currentText()
            else:
                out[key] = widget.text()
        return out

    def _browse_image(self) -> None:
        start = templates_dir()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Template image",
            str(start),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if path:
            self._image_path.setText(path)

    def _set_all_hidden(self) -> None:
        for row in self._rows.values():
            row.hide()
        self._btn_region.hide()

    def _sync_visibility(self, kind: ActionType) -> None:
        """Show only rows that apply to this action type."""
        show: set[str] = set()
        if kind in (ActionType.MOUSE_CLICK, ActionType.MOUSE_MOVE):
            show.update({"x", "y"})
        if kind == ActionType.MOUSE_CLICK:
            show.update({"button", "phase_click"})
        if kind == ActionType.MOUSE_DRAG:
            show.update({"x", "y", "end_x", "end_y", "button", "hold_ms"})
        if kind == ActionType.KEY:
            show.update({"key", "phase_key"})
        if kind == ActionType.HOTKEY:
            show.add("keys")
        if kind == ActionType.HOLD:
            show.update({"key", "button", "x", "y", "hold_ms"})
        if kind == ActionType.DELAY:
            show.add("delay_ms")
        if kind in (ActionType.FIND_TEXT, ActionType.WAIT_TEXT, ActionType.IF_TEXT):
            show.update(
                {
                    "query",
                    "timeout_ms",
                    "region_x",
                    "region_y",
                    "region_w",
                    "region_h",
                    "capture_monitor",
                }
            )
            if kind == ActionType.FIND_TEXT:
                show.update({"button", "on_fail"})
            elif kind == ActionType.WAIT_TEXT:
                show.add("on_fail")
        if kind in (ActionType.FIND_IMAGE, ActionType.WAIT_IMAGE, ActionType.IF_IMAGE):
            show.update(
                {
                    "image_path",
                    "threshold",
                    "timeout_ms",
                    "region_x",
                    "region_y",
                    "region_w",
                    "region_h",
                    "capture_monitor",
                }
            )
            if kind == ActionType.FIND_IMAGE:
                show.update({"button", "on_fail"})
            elif kind == ActionType.WAIT_IMAGE:
                show.add("on_fail")

        for key, row in self._rows.items():
            row.setVisible(key in show)
        self._btn_region.setVisible(kind in VISION_TYPES)

    @staticmethod
    def title_for(action: Action) -> str:
        return format_step_title(action)
