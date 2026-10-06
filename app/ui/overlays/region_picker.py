"""Fullscreen drag picker for a capture rectangle on one monitor."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QRubberBand, QWidget

from app.core.monitors import get_monitor


class RegionPickerOverlay(QWidget):
    """Dim overlay on one monitor; drag to select. Esc cancels."""

    region_selected = Signal(int, int, int, int)
    cancelled = Signal()

    def __init__(self, monitor_index: int, parent=None) -> None:
        # Keep as tool window on top, but never true OS fullscreen (traps the desktop).
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFocusPolicy(Qt.StrongFocus)

        mon = get_monitor(monitor_index)
        self.setGeometry(mon.x, mon.y, mon.width, mon.height)
        self.setWindowOpacity(0.45)
        self.setStyleSheet("background: #0a0a12;")
        self.setCursor(Qt.CrossCursor)

        self._origin = None
        self._band = QRubberBand(QRubberBand.Rectangle, self)
        self._finished = False

        self._hint = QLabel("Drag to select capture region · Esc to cancel", self)
        self._hint.setStyleSheet(
            "color: #60A5FA; font-size: 16px; font-weight: 600; background: transparent;"
        )
        self._hint.adjustSize()
        self._hint.move(max(16, (mon.width - self._hint.width()) // 2), 40)

    def show_picker(self) -> None:
        """Show overlay on the target monitor and take focus."""
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)
        # Ensure Esc works even if focus races
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self._cancel()
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        self._origin = event.position().toPoint()
        self._band.setGeometry(self._origin.x(), self._origin.y(), 0, 0)
        self._band.show()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is None:
            return
        p = event.position().toPoint()
        x = min(self._origin.x(), p.x())
        y = min(self._origin.y(), p.y())
        w = abs(p.x() - self._origin.x())
        h = abs(p.y() - self._origin.y())
        self._band.setGeometry(x, y, w, h)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._origin is None or event.button() != Qt.LeftButton:
            return
        rect = self._band.geometry()
        self._band.hide()
        self._origin = None
        if rect.width() >= 4 and rect.height() >= 4:
            self._finish_ok(rect.x(), rect.y(), rect.width(), rect.height())
        else:
            self._cancel()

    def closeEvent(self, event) -> None:  # noqa: N802
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        if not self._finished:
            self._finished = True
            self.cancelled.emit()
        super().closeEvent(event)

    def _finish_ok(self, x: int, y: int, w: int, h: int) -> None:
        if self._finished:
            return
        self._finished = True
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.region_selected.emit(x, y, w, h)
        self.close()

    def _cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.cancelled.emit()
        self.close()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._band.isVisible():
            painter = QPainter(self)
            painter.setPen(QPen(QColor("#3B82F6"), 2))
            painter.drawRect(self._band.geometry())
