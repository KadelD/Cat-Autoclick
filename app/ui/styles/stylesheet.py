"""Global Qt stylesheet from design tokens."""

from __future__ import annotations

from app.ui.styles.tokens import Colors, Control, Font, Radius


def build_stylesheet() -> str:
    """Return application-wide QSS for the dark IDE shell."""
    c = Colors
    return f"""
    * {{
        outline: none;
    }}
    QWidget {{
        color: {c.TEXT};
        font-family: {Font.FAMILY};
        font-size: {Font.BODY}px;
    }}
    QMainWindow, QDialog {{
        background-color: {c.APP_BG};
    }}
    QSplitter {{
        background: {c.APP_BG};
    }}
    /* Labels / badges sit on panels — never paint their own opaque block. */
    QLabel, QFrame#statusBadge {{
        background: transparent;
        border: none;
    }}
    QToolTip {{
        background: {c.SURFACE};
        color: {c.TEXT};
        border: 1px solid {c.BORDER};
        padding: 4px 8px;
        border-radius: {Radius.SM}px;
    }}
    QSplitter::handle {{
        background: {c.BORDER};
        width: 1px;
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {c.INPUT};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.SM}px;
        padding: 4px 8px;
        min-height: {Control.HEIGHT_SM}px;
        max-height: {Control.HEIGHT}px;
        color: {c.TEXT};
        selection-background-color: {c.ACCENT};
        selection-color: white;
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDoubleSpinBox:focus {{
        border-color: {c.BORDER_FOCUS};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
        color: {c.TEXT_DISABLED};
        background: {c.PANEL};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        selection-background-color: {c.SURFACE_SELECTED};
        outline: none;
    }}
    QPushButton {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.SM}px;
        padding: 4px 12px;
        min-height: {Control.HEIGHT_SM}px;
        max-height: {Control.HEIGHT}px;
        color: {c.TEXT};
        font-size: {Font.BUTTON}px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background: {c.SURFACE_HOVER};
        border-color: {c.BORDER_STRONG};
    }}
    QPushButton:pressed {{
        background: {c.SURFACE_SELECTED};
    }}
    QPushButton:disabled {{
        color: {c.TEXT_DISABLED};
        background: {c.PANEL};
        border-color: {c.BORDER};
    }}
    QPushButton#primary {{
        background: {c.ACCENT};
        color: white;
        border: none;
        font-weight: 600;
    }}
    QPushButton#primary:hover {{
        background: {c.ACCENT_HOVER};
    }}
    QPushButton#primary:pressed {{
        background: {c.ACCENT_PRESSED};
    }}
    QPushButton#secondary {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        color: {c.TEXT};
    }}
    QPushButton#ghost {{
        background: transparent;
        border: 1px solid transparent;
        color: {c.TEXT_SECONDARY};
    }}
    QPushButton#ghost:hover {{
        background: {c.SURFACE_HOVER};
        border-color: {c.BORDER};
        color: {c.TEXT};
    }}
    QPushButton#danger {{
        background: transparent;
        border: 1px solid rgba(239, 68, 68, 0.45);
        color: {c.ERROR};
    }}
    QPushButton#danger:hover {{
        background: rgba(239, 68, 68, 0.1);
        border-color: {c.ERROR};
    }}
    QPushButton#icon {{
        background: transparent;
        border: 1px solid transparent;
        padding: 4px;
        min-width: {Control.BTN_ICON}px;
        max-width: {Control.BTN_ICON}px;
        min-height: {Control.BTN_ICON}px;
        max-height: {Control.BTN_ICON}px;
    }}
    QPushButton#icon:hover {{
        background: {c.SURFACE_HOVER};
        border-color: {c.BORDER};
    }}
    QTreeView, QListWidget {{
        background: transparent;
        border: none;
        outline: none;
        padding: 2px;
    }}
    QTreeView::item {{
        min-height: 48px;
        border: none;
        padding: 0;
    }}
    QTreeView::item:selected {{
        background: transparent;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: {Radius.SM}px;
        margin: 1px 0;
        color: {c.TEXT_SECONDARY};
    }}
    QListWidget::item:hover {{
        background: {c.SURFACE_HOVER};
        color: {c.TEXT};
    }}
    QListWidget::item:selected {{
        background: {c.ACCENT_SOFT};
        color: {c.TEXT};
        border: 1px solid {c.ACCENT_SOFT_BORDER};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c.BORDER_STRONG};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        height: 0;
    }}
    QStatusBar {{
        background: {c.PANEL};
        border-top: 1px solid {c.BORDER};
        color: {c.TEXT_MUTED};
        font-size: {Font.META}px;
    }}
    QStatusBar::item {{
        border: none;
    }}
    QMenu {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        padding: 4px;
        color: {c.TEXT};
    }}
    QMenu::item {{
        padding: 6px 28px 6px 12px;
        border-radius: {Radius.SM}px;
    }}
    QMenu::item:selected {{
        background: {c.SURFACE_HOVER};
    }}
    QMenu::separator {{
        height: 1px;
        background: {c.BORDER};
        margin: 4px 8px;
    }}
    QCheckBox {{
        spacing: 8px;
        color: {c.TEXT};
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {c.BORDER_STRONG};
        border-radius: 3px;
        background: {c.INPUT};
    }}
    QCheckBox::indicator:checked {{
        background: {c.ACCENT};
        border-color: {c.ACCENT};
    }}
    QLabel#section {{
        color: {c.TEXT_MUTED};
        font-size: {Font.SECTION}px;
        font-weight: 600;
        letter-spacing: 0.8px;
    }}
    QLabel#hint {{
        color: {c.TEXT_MUTED};
        font-size: {Font.META}px;
    }}
    QFrame#panel {{
        background: {c.PANEL};
        border: none;
    }}
    """
