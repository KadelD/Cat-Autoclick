"""Reusable UI primitives for Cat Automation Studio."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from app.ui.styles.icons import icon
from app.ui.styles.tokens import Colors, Control


class AppButton(QPushButton):
    """Button with variant: primary | secondary | ghost | danger."""

    def __init__(self, text: str = "", *, variant: str = "secondary", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName(variant)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(Control.HEIGHT_SM)


class IconButton(QPushButton):
    """Compact icon-only button with tooltip."""

    def __init__(self, icon_name: str, tooltip: str = "", *, color: str = Colors.TEXT_SECONDARY, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("icon")
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(icon(icon_name, Control.ICON, color))
        self.setIconSize(QSize(Control.ICON, Control.ICON))
        if tooltip:
            self.setToolTip(tooltip)
        self.setFixedSize(Control.BTN_ICON, Control.BTN_ICON)


class SearchField(QWidget):
    """Search input with vector search icon."""

    def __init__(self, placeholder: str = "Search…", parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        wrap = QWidget()
        wrap.setObjectName("searchWrap")
        wrap.setStyleSheet(
            f"""
            QWidget#searchWrap {{
                background: {Colors.INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
            }}
            QWidget#searchWrap:focus-within {{
                border-color: {Colors.BORDER_FOCUS};
            }}
            """
        )
        inner = QHBoxLayout(wrap)
        inner.setContentsMargins(8, 0, 8, 0)
        inner.setSpacing(6)

        icon_lab = QLabel()
        icon_lab.setPixmap(icon("search", 14, Colors.TEXT_MUTED).pixmap(14, 14))
        icon_lab.setFixedSize(14, 14)
        inner.addWidget(icon_lab)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFrame(False)
        self.edit.setStyleSheet(
            f"background: transparent; border: none; color: {Colors.TEXT}; padding: 6px 0;"
        )
        self.edit.setFixedHeight(Control.HEIGHT_SM)
        inner.addWidget(self.edit, stretch=1)
        layout.addWidget(wrap)

    def text(self) -> str:
        return self.edit.text()

    def textChanged(self):
        return self.edit.textChanged


class StatusBadge(QFrame):
    """Quiet status pill: Ready / Recording / Running / Paused / Error."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBadge")
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Must paint via QSS as transparent — otherwise QFrame fills palette Window (APP_BG).
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet(
            "QFrame#statusBadge { background: transparent; border: none; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._dot = QFrame()
        self._dot.setObjectName("statusDot")
        self._dot.setFrameShape(QFrame.Shape.NoFrame)
        self._dot.setAttribute(Qt.WA_StyledBackground, True)
        self._dot.setFixedSize(7, 7)
        self._label = QLabel("Ready")
        self._label.setAttribute(Qt.WA_TranslucentBackground, True)
        self._label.setAutoFillBackground(False)
        self._label.setStyleSheet(
            f"background: transparent; border: none; color: {Colors.TEXT_SECONDARY}; "
            f"font-weight: 500; font-size: 12px;"
        )
        layout.addWidget(self._dot, 0, Qt.AlignVCenter)
        layout.addWidget(self._label)
        self.set_status("ready")

    def set_status(self, kind: str) -> None:
        """kind: ready|recording|running|paused|error."""
        mapping = {
            "ready": (Colors.SUCCESS, "Ready"),
            "recording": (Colors.RECORD, "Recording"),
            "running": (Colors.ACCENT, "Running"),
            "paused": (Colors.WARNING, "Paused"),
            "error": (Colors.ERROR, "Error"),
        }
        color, text = mapping.get(kind, (Colors.TEXT_MUTED, kind.title()))
        self._dot.setStyleSheet(
            f"QFrame#statusDot {{ background: {color}; border: none; border-radius: 3px; }}"
        )
        self._label.setText(text)
        self._label.setStyleSheet(
            f"background: transparent; border: none; color: {Colors.TEXT_SECONDARY}; "
            f"font-weight: 500; font-size: 12px;"
        )


class SectionHeader(QLabel):
    """Muted uppercase section label."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("section")
