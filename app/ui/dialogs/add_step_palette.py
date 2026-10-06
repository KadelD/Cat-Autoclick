"""Searchable command palette for inserting workflow steps."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from app.core.models import ActionType
from app.ui.styles.icons import step_icon_for_type
from app.ui.styles.tokens import Colors, Control


@dataclass(frozen=True)
class StepPaletteEntry:
    """One selectable action in the palette."""

    category: str
    label: str
    description: str
    action_type: ActionType


PALETTE_ENTRIES: list[StepPaletteEntry] = [
    StepPaletteEntry("Mouse", "Mouse Click", "Click at X/Y on the monitor", ActionType.MOUSE_CLICK),
    StepPaletteEntry("Mouse", "Mouse Move", "Move cursor to coordinates", ActionType.MOUSE_MOVE),
    StepPaletteEntry("Mouse", "Mouse Drag", "Drag between two points", ActionType.MOUSE_DRAG),
    StepPaletteEntry("Keyboard", "Press Key", "Single key tap / press / release", ActionType.KEY),
    StepPaletteEntry("Keyboard", "Hotkey", "Key chord such as Ctrl+Shift+S", ActionType.HOTKEY),
    StepPaletteEntry("Keyboard", "Hold", "Hold a key or mouse button", ActionType.HOLD),
    StepPaletteEntry("Timing", "Wait", "Delay for milliseconds", ActionType.DELAY),
    StepPaletteEntry("Vision", "Find Text & Click", "OCR then click", ActionType.FIND_TEXT),
    StepPaletteEntry("Vision", "Wait for Text", "Wait until text appears", ActionType.WAIT_TEXT),
    StepPaletteEntry("Vision", "Find Image & Click", "Template match then click", ActionType.FIND_IMAGE),
    StepPaletteEntry("Vision", "Wait for Image", "Wait until image appears", ActionType.WAIT_IMAGE),
    StepPaletteEntry("Logic", "If Text", "Branch when text is found", ActionType.IF_TEXT),
    StepPaletteEntry("Logic", "If Image", "Branch when image is found", ActionType.IF_IMAGE),
    StepPaletteEntry("Logic", "Else", "Else branch for open If", ActionType.ELSE),
    StepPaletteEntry("Logic", "End If", "Close the nearest If block", ActionType.ENDIF),
]


class AddStepPaletteDialog(QDialog):
    """Filterable list of step types; Enter confirms selection."""

    step_chosen = Signal(object)  # ActionType

    def __init__(self, parent=None, *, ocr_enabled: bool = True) -> None:
        super().__init__(parent)
        self._ocr_enabled = ocr_enabled
        self.setWindowTitle("Add Step")
        self.setModal(True)
        self.resize(420, 480)
        self.setStyleSheet(f"background: {Colors.PANEL}; color: {Colors.TEXT};")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search actions…")
        self._search.textChanged.connect(self._refilter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setIconSize(QSize(Control.ICON, Control.ICON))
        self._list.itemActivated.connect(self._activate)
        layout.addWidget(self._list, stretch=1)

        hint = QLabel("Up/Down navigate · Enter add · Esc cancel")
        hint.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(hint)

        self._build_items()
        self._search.setFocus()

    def _entry_icon(self, action_type: ActionType) -> QIcon:
        return QIcon(step_icon_for_type(action_type, Control.ICON, Colors.TEXT_SECONDARY))

    def _build_items(self) -> None:
        """Populate list with category headers and entries."""
        self._list.clear()
        last_cat = ""
        for entry in PALETTE_ENTRIES:
            if not self._ocr_enabled and entry.action_type.name.endswith("_TEXT"):
                continue
            if entry.category != last_cat:
                last_cat = entry.category
                head = QListWidgetItem(entry.category)
                head.setFlags(Qt.NoItemFlags)
                head.setForeground(Qt.gray)
                self._list.addItem(head)
            item = QListWidgetItem(entry.label)
            item.setIcon(self._entry_icon(entry.action_type))
            item.setToolTip(entry.description)
            item.setData(Qt.UserRole, entry.action_type)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(1)

    def _refilter(self, text: str) -> None:
        """Show entries matching search text."""
        q = text.strip().lower()
        self._list.clear()
        last_cat = ""
        for entry in PALETTE_ENTRIES:
            if not self._ocr_enabled and entry.action_type.name.endswith("_TEXT"):
                continue
            blob = f"{entry.category} {entry.label} {entry.description}".lower()
            if q and q not in blob:
                continue
            if entry.category != last_cat:
                last_cat = entry.category
                head = QListWidgetItem(entry.category)
                head.setFlags(Qt.NoItemFlags)
                self._list.addItem(head)
            item = QListWidgetItem(entry.label)
            item.setIcon(self._entry_icon(entry.action_type))
            item.setData(Qt.UserRole, entry.action_type)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._list.addItem(item)

    def _activate(self, item: QListWidgetItem) -> None:
        at = item.data(Qt.UserRole)
        if at is None:
            return
        self.step_chosen.emit(at)
        self.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self._list.currentItem()
            if item:
                self._activate(item)
            return
        super().keyPressEvent(event)

    @staticmethod
    def pick(parent=None, *, ocr_enabled: bool = True) -> ActionType | None:
        """Modal helper; returns chosen ActionType or None."""
        dlg = AddStepPaletteDialog(parent, ocr_enabled=ocr_enabled)
        chosen: list[ActionType] = []

        def on_pick(at: ActionType) -> None:
            chosen.append(at)

        dlg.step_chosen.connect(on_pick)
        if dlg.exec() == QDialog.Accepted and chosen:
            return chosen[0]
        return None
