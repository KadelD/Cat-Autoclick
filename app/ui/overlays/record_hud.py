"""Floating Qt HUD shown while recording."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.core.monitors import get_monitor
from app.core.settings import AppSettings, get_settings
from app.ui.styles.tokens import Colors


class RecordHud(QFrame):
    """Small topmost panel with recording tips."""

    def __init__(self, monitor_index: int = 0, settings: AppSettings | None = None) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(
            f"background: {Colors.PANEL}; border: 1px solid {Colors.BORDER}; border-radius: 8px;"
        )
        mon = get_monitor(monitor_index)
        width, height = 260, 180
        x = mon.x + mon.width - width - 16
        y = mon.y + 48
        self.setGeometry(x, y, width, height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        self._title = QLabel("Recording…")
        self._title.setStyleSheet(f"color: {Colors.RECORD}; font-size: 13px; font-weight: 600;")
        layout.addWidget(self._title)
        self._body = QLabel(_tips_text(settings or get_settings()))
        self._body.setWordWrap(True)
        self._body.setStyleSheet(f"color: {Colors.TEXT}; font-size: 11px;")
        layout.addWidget(self._body)

    def set_status(self, message: str) -> None:
        """Update title line."""
        self._title.setText(message)

    def show_hud(self) -> None:
        """Show above other windows."""
        self.show()
        self.raise_()


def _tips_text(settings: AppSettings) -> str:
    """Build HUD tip lines from hotkey settings."""
    lines = [
        f"{settings.display_hotkey('record')}  stop record",
        f"{settings.display_hotkey('stop')}  stop all",
    ]
    if settings.ocr_enabled:
        lines.append(f"{settings.display_hotkey('ocr_full')}  OCR full screen")
        lines.append(f"{settings.display_hotkey('ocr_area')}  OCR area")
    return "\n".join(lines)
