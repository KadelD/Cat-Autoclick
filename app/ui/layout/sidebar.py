"""Preset navigation sidebar."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QListWidget, QVBoxLayout

from app import __version__
from app.ui.styles.tokens import Colors
from app.ui.widgets import AppButton, SearchField, SectionHeader


class PresetSidebar(QFrame):
    """Lists presets with search and new-macro action."""

    preset_selected = Signal(str)
    new_macro_requested = Signal()
    settings_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)
        self.setStyleSheet(
            f"QFrame#panel {{ background: {Colors.PANEL}; border-right: 1px solid {Colors.BORDER}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(SectionHeader("Presets"))

        self.btn_new = AppButton("+ New Macro", variant="primary")
        self.btn_new.clicked.connect(self.new_macro_requested.emit)
        layout.addWidget(self.btn_new)

        self.search = SearchField("Search presets…")
        self.search.textChanged().connect(self._on_search)
        layout.addWidget(self.search)

        layout.addWidget(SectionHeader("Recent"))

        self.list = QListWidget()
        self.list.setFrameShape(QListWidget.NoFrame)
        self.list.currentRowChanged.connect(self._on_row)
        layout.addWidget(self.list, stretch=1)

        foot = QLabel(f"v{__version__}")
        foot.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(foot)

        self._ids: list[str] = []
        self._filter = ""
        self._all_names: list[str] = []
        self._all_ids: list[str] = []

    def set_presets(self, names: list[str], ids: list[str], selected_id: str | None) -> None:
        """Populate list; ids parallel to names."""
        self._all_names = names
        self._all_ids = ids
        self._filter = self.search.text().strip().lower()
        self._rebuild(selected_id)

    def _on_search(self, text: str) -> None:
        self._filter = text.strip().lower()
        self._rebuild(None)

    def _rebuild(self, selected_id: str | None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        self._ids = []
        for name, pid in zip(self._all_names, self._all_ids, strict=True):
            if self._filter and self._filter not in name.lower():
                continue
            self.list.addItem(name)
            self._ids.append(pid)
        if selected_id and selected_id in self._ids:
            self.list.setCurrentRow(self._ids.index(selected_id))
        self.list.blockSignals(False)

    def _on_row(self, row: int) -> None:
        if 0 <= row < len(self._ids):
            self.preset_selected.emit(self._ids[row])
