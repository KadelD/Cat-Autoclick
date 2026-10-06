"""Vector icon factory drawn with QPainter (no emoji, no external assets)."""

from __future__ import annotations

import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from app.core.models import Action, ActionType
from app.ui.styles.tokens import Colors, Control


def _pen(color: str, width: float = 1.6) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _pixmap(size: int, drawer, color: str) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    drawer(p, float(size), color)
    p.end()
    return pm


def _draw_mouse_click(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    # simple mouse outline
    p.drawRoundedRect(QRectF(s * 0.32, s * 0.18, s * 0.36, s * 0.58), s * 0.12, s * 0.12)
    p.drawLine(QPointF(s * 0.5, s * 0.18), QPointF(s * 0.5, s * 0.42))
    # click dot
    p.setBrush(QColor(color))
    p.drawEllipse(QPointF(s * 0.72, s * 0.72), s * 0.08, s * 0.08)


def _draw_mouse_move(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    # arrow NE
    p.drawLine(QPointF(s * 0.28, s * 0.72), QPointF(s * 0.72, s * 0.28))
    p.drawLine(QPointF(s * 0.48, s * 0.28), QPointF(s * 0.72, s * 0.28))
    p.drawLine(QPointF(s * 0.72, s * 0.28), QPointF(s * 0.72, s * 0.52))


def _draw_mouse_drag(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.78, s * 0.5))
    p.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.34, s * 0.38))
    p.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.34, s * 0.62))
    p.drawLine(QPointF(s * 0.78, s * 0.5), QPointF(s * 0.66, s * 0.38))
    p.drawLine(QPointF(s * 0.78, s * 0.5), QPointF(s * 0.66, s * 0.62))


def _draw_key(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(s * 0.18, s * 0.28, s * 0.64, s * 0.44), 3, 3)
    p.drawLine(QPointF(s * 0.3, s * 0.5), QPointF(s * 0.7, s * 0.5))


def _draw_hotkey(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.34, s * 0.32, s * 0.32), 2, 2)
    p.drawRoundedRect(QRectF(s * 0.54, s * 0.34, s * 0.32, s * 0.32), 2, 2)


def _draw_hold(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color, 2.0))
    p.drawLine(QPointF(s * 0.36, s * 0.28), QPointF(s * 0.36, s * 0.72))
    p.drawLine(QPointF(s * 0.64, s * 0.28), QPointF(s * 0.64, s * 0.72))


def _draw_wait(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6))
    p.drawLine(QPointF(s * 0.5, s * 0.32), QPointF(s * 0.5, s * 0.5))
    p.drawLine(QPointF(s * 0.5, s * 0.5), QPointF(s * 0.66, s * 0.58))


def _draw_search(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(s * 0.22, s * 0.22, s * 0.42, s * 0.42))
    p.drawLine(QPointF(s * 0.56, s * 0.56), QPointF(s * 0.78, s * 0.78))


def _draw_image(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(s * 0.2, s * 0.26, s * 0.6, s * 0.48), 2, 2)
    p.drawEllipse(QPointF(s * 0.36, s * 0.42), s * 0.06, s * 0.06)
    path = QPainterPath()
    path.moveTo(s * 0.28, s * 0.66)
    path.lineTo(s * 0.44, s * 0.5)
    path.lineTo(s * 0.56, s * 0.6)
    path.lineTo(s * 0.72, s * 0.44)
    p.drawPath(path)


def _draw_text(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color, 1.8))
    p.drawLine(QPointF(s * 0.28, s * 0.3), QPointF(s * 0.72, s * 0.3))
    p.drawLine(QPointF(s * 0.5, s * 0.3), QPointF(s * 0.5, s * 0.72))


def _draw_condition(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(s * 0.5, s * 0.18)
    path.lineTo(s * 0.82, s * 0.5)
    path.lineTo(s * 0.5, s * 0.82)
    path.lineTo(s * 0.18, s * 0.5)
    path.closeSubpath()
    p.drawPath(path)


def _draw_else(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.drawLine(QPointF(s * 0.28, s * 0.28), QPointF(s * 0.28, s * 0.72))
    p.drawLine(QPointF(s * 0.28, s * 0.5), QPointF(s * 0.72, s * 0.5))
    p.drawLine(QPointF(s * 0.72, s * 0.5), QPointF(s * 0.58, s * 0.38))
    p.drawLine(QPointF(s * 0.72, s * 0.5), QPointF(s * 0.58, s * 0.62))


def _draw_endif(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(s * 0.28, s * 0.28, s * 0.44, s * 0.44))


def _draw_record(p: QPainter, s: float, color: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.22, s * 0.22)


def _draw_play(p: QPainter, s: float, color: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(s * 0.34, s * 0.24)
    path.lineTo(s * 0.78, s * 0.5)
    path.lineTo(s * 0.34, s * 0.76)
    path.closeSubpath()
    p.drawPath(path)


def _draw_pause(p: QPainter, s: float, color: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(s * 0.3, s * 0.26, s * 0.14, s * 0.48), 1, 1)
    p.drawRoundedRect(QRectF(s * 0.56, s * 0.26, s * 0.14, s * 0.48), 1, 1)


def _draw_stop(p: QPainter, s: float, color: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(s * 0.3, s * 0.3, s * 0.4, s * 0.4), 2, 2)


def _draw_settings(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(s * 0.34, s * 0.34, s * 0.32, s * 0.32))
    # simple gear teeth as lines
    for a in range(0, 360, 45):
        rad = math.radians(a)
        cx, cy = s * 0.5, s * 0.5
        p.drawLine(
            QPointF(cx + math.cos(rad) * s * 0.22, cy + math.sin(rad) * s * 0.22),
            QPointF(cx + math.cos(rad) * s * 0.36, cy + math.sin(rad) * s * 0.36),
        )


def _draw_add(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color, 1.8))
    p.drawLine(QPointF(s * 0.5, s * 0.24), QPointF(s * 0.5, s * 0.76))
    p.drawLine(QPointF(s * 0.24, s * 0.5), QPointF(s * 0.76, s * 0.5))


def _draw_delete(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.drawLine(QPointF(s * 0.28, s * 0.32), QPointF(s * 0.72, s * 0.32))
    p.drawLine(QPointF(s * 0.36, s * 0.32), QPointF(s * 0.4, s * 0.74))
    p.drawLine(QPointF(s * 0.64, s * 0.32), QPointF(s * 0.6, s * 0.74))
    p.drawLine(QPointF(s * 0.4, s * 0.74), QPointF(s * 0.6, s * 0.74))
    p.drawLine(QPointF(s * 0.42, s * 0.24), QPointF(s * 0.58, s * 0.24))


def _draw_duplicate(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(s * 0.22, s * 0.28, s * 0.42, s * 0.42), 2, 2)
    p.drawRoundedRect(QRectF(s * 0.36, s * 0.18, s * 0.42, s * 0.42), 2, 2)


def _draw_save(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(s * 0.24, s * 0.24)
    path.lineTo(s * 0.64, s * 0.24)
    path.lineTo(s * 0.76, s * 0.36)
    path.lineTo(s * 0.76, s * 0.76)
    path.lineTo(s * 0.24, s * 0.76)
    path.closeSubpath()
    p.drawPath(path)
    p.drawRect(QRectF(s * 0.34, s * 0.5, s * 0.32, s * 0.26))


def _draw_more(p: QPainter, s: float, color: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    for x in (0.3, 0.5, 0.7):
        p.drawEllipse(QPointF(s * x, s * 0.5), s * 0.07, s * 0.07)


def _draw_grip(p: QPainter, s: float, color: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    for y in (0.32, 0.5, 0.68):
        p.drawEllipse(QPointF(s * 0.38, s * y), s * 0.055, s * 0.055)
        p.drawEllipse(QPointF(s * 0.62, s * y), s * 0.055, s * 0.055)


def _draw_warning(p: QPainter, s: float, color: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(s * 0.5, s * 0.2)
    path.lineTo(s * 0.82, s * 0.76)
    path.lineTo(s * 0.18, s * 0.76)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(s * 0.5, s * 0.4), QPointF(s * 0.5, s * 0.56))
    p.setBrush(QColor(color))
    p.drawEllipse(QPointF(s * 0.5, s * 0.66), s * 0.04, s * 0.04)


def _draw_brand(p: QPainter, s: float, color: str) -> None:
    """Minimal geometric mark (stylized C / precision)."""
    p.setPen(_pen(color, 1.8))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6), 50 * 16, 260 * 16)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.1, s * 0.1)


_DRAWERS = {
    "mouse_click": _draw_mouse_click,
    "mouse_move": _draw_mouse_move,
    "mouse_drag": _draw_mouse_drag,
    "key": _draw_key,
    "hotkey": _draw_hotkey,
    "hold": _draw_hold,
    "wait": _draw_wait,
    "search": _draw_search,
    "find_text": _draw_search,
    "find_image": _draw_image,
    "wait_text": _draw_search,
    "wait_image": _draw_image,
    "if_text": _draw_condition,
    "if_image": _draw_condition,
    "else": _draw_else,
    "endif": _draw_endif,
    "record": _draw_record,
    "play": _draw_play,
    "pause": _draw_pause,
    "stop": _draw_stop,
    "settings": _draw_settings,
    "add": _draw_add,
    "delete": _draw_delete,
    "duplicate": _draw_duplicate,
    "save": _draw_save,
    "more": _draw_more,
    "grip": _draw_grip,
    "warning": _draw_warning,
    "brand": _draw_brand,
    "text": _draw_text,
    "image": _draw_image,
}

_STEP_ICON_KEYS: dict[ActionType, str] = {
    ActionType.MOUSE_CLICK: "mouse_click",
    ActionType.MOUSE_MOVE: "mouse_move",
    ActionType.MOUSE_DRAG: "mouse_drag",
    ActionType.KEY: "key",
    ActionType.HOTKEY: "hotkey",
    ActionType.HOLD: "hold",
    ActionType.DELAY: "wait",
    ActionType.FIND_TEXT: "find_text",
    ActionType.FIND_IMAGE: "find_image",
    ActionType.WAIT_TEXT: "wait_text",
    ActionType.WAIT_IMAGE: "wait_image",
    ActionType.IF_TEXT: "if_text",
    ActionType.IF_IMAGE: "if_image",
    ActionType.ELSE: "else",
    ActionType.ENDIF: "endif",
}


@lru_cache(maxsize=256)
def icon_pixmap(name: str, size: int = Control.ICON, color: str = Colors.TEXT_SECONDARY) -> QPixmap:
    """Return a cached pixmap for a named icon."""
    drawer = _DRAWERS.get(name, _draw_more)
    return _pixmap(size, drawer, color)


def icon(name: str, size: int = Control.ICON, color: str = Colors.TEXT_SECONDARY) -> QIcon:
    """Return a QIcon for toolbar / buttons."""
    return QIcon(icon_pixmap(name, size, color))


def step_icon_key(action_type: ActionType) -> str:
    """Map ActionType → icon registry key."""
    return _STEP_ICON_KEYS.get(action_type, "more")


def step_icon_for_action(action: Action, size: int = Control.ICON, color: str = Colors.TEXT) -> QPixmap:
    """Pixmap for a workflow step."""
    return icon_pixmap(step_icon_key(action.type), size, color)


def step_icon_for_type(action_type: ActionType, size: int = Control.ICON, color: str = Colors.TEXT) -> QPixmap:
    """Pixmap for an action type."""
    return icon_pixmap(step_icon_key(action_type), size, color)
