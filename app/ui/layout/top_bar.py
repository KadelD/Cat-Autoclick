"""Application toolbar — brand, macro, status, transport."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel

from app.application.app_state import AppState
from app.ui.styles.icons import icon
from app.ui.styles.tokens import Colors, Control
from app.ui.widgets import AppButton, IconButton, StatusBadge


class TopBar(QFrame):
    """Top bar with Record / Run / Pause / Stop driven by AppState."""

    record_clicked = Signal()
    run_clicked = Signal()
    pause_clicked = Signal()
    stop_clicked = Signal()
    settings_clicked = Signal()
    macro_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("topBar")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet(
            f"""
            QFrame#topBar {{
                background: {Colors.PANEL};
                border: none;
                border-bottom: 1px solid {Colors.BORDER};
            }}
            QFrame#topBar QLabel,
            QFrame#topBar QFrame#statusBadge {{
                background: transparent;
                border: none;
            }}
            """
        )
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        brand_icon = QLabel()
        brand_icon.setAttribute(Qt.WA_TranslucentBackground, True)
        brand_icon.setAutoFillBackground(False)
        brand_icon.setPixmap(icon("brand", 18, Colors.ACCENT).pixmap(18, 18))
        brand_icon.setFixedSize(18, 18)
        layout.addWidget(brand_icon)

        brand = QLabel("Cat Automation Studio")
        brand.setAttribute(Qt.WA_TranslucentBackground, True)
        brand.setAutoFillBackground(False)
        brand.setStyleSheet(
            f"background: transparent; border: none; font-size: 14px; font-weight: 600; "
            f"color: {Colors.TEXT}; letter-spacing: -0.2px;"
        )
        layout.addWidget(brand)

        self.macro_combo = QComboBox()
        self.macro_combo.setMinimumWidth(160)
        self.macro_combo.setMaximumWidth(240)
        self.macro_combo.currentIndexChanged.connect(self._on_macro)
        layout.addWidget(self.macro_combo)

        self.status = StatusBadge()
        layout.addWidget(self.status)

        layout.addStretch(1)

        self.btn_record = AppButton("Record", variant="primary")
        self.btn_record.setIcon(icon("record", 14, "#FFFFFF"))
        self.btn_record.setToolTip("Start / stop recording")
        self.btn_record.clicked.connect(self.record_clicked.emit)
        layout.addWidget(self.btn_record)

        self.btn_run = AppButton("Run", variant="secondary")
        self.btn_run.setIcon(icon("play", 14, Colors.TEXT))
        self.btn_run.clicked.connect(self.run_clicked.emit)
        layout.addWidget(self.btn_run)

        self.btn_pause = AppButton("Pause", variant="ghost")
        self.btn_pause.setIcon(icon("pause", 14, Colors.TEXT_SECONDARY))
        self.btn_pause.clicked.connect(self.pause_clicked.emit)
        self.btn_pause.hide()
        layout.addWidget(self.btn_pause)

        self.btn_stop = AppButton("Stop", variant="ghost")
        self.btn_stop.setIcon(icon("stop", 14, Colors.TEXT_SECONDARY))
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_stop.hide()
        layout.addWidget(self.btn_stop)

        self.btn_settings = IconButton("settings", "Settings")
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.btn_settings)

    def set_macros(self, names: list[str], selected_id: str | None, id_by_index: list[str]) -> None:
        """Refresh macro dropdown."""
        self._ids = id_by_index
        self.macro_combo.blockSignals(True)
        self.macro_combo.clear()
        self.macro_combo.addItems(names)
        if selected_id and selected_id in id_by_index:
            self.macro_combo.setCurrentIndex(id_by_index.index(selected_id))
        self.macro_combo.blockSignals(False)

    def _on_macro(self, index: int) -> None:
        if 0 <= index < len(getattr(self, "_ids", [])):
            self.macro_changed.emit(self._ids[index])

    def set_app_state(self, state: AppState) -> None:
        """Show valid transport buttons for current mode."""
        self.btn_record.hide()
        self.btn_run.hide()
        self.btn_pause.hide()
        self.btn_stop.hide()

        if state == AppState.IDLE:
            self.status.set_status("ready")
            self.btn_record.show()
            self.btn_run.show()
        elif state == AppState.RECORDING:
            self.status.set_status("recording")
            self.btn_stop.setText("Stop Recording")
            self.btn_stop.show()
        elif state == AppState.PLAYING:
            self.status.set_status("running")
            self.btn_pause.setText("Pause")
            self.btn_pause.show()
            self.btn_stop.setText("Stop")
            self.btn_stop.show()
        elif state == AppState.PAUSED:
            self.status.set_status("paused")
            self.btn_pause.setText("Resume")
            self.btn_pause.show()
            self.btn_stop.show()
        elif state == AppState.ERROR:
            self.status.set_status("error")
            self.btn_record.show()
            self.btn_run.show()
