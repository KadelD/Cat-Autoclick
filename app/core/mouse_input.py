"""Inject mouse motion via Win32 SendInput (not SetCursorPos).

pynput's ``Controller.position = …`` calls SetCursorPos, which moves the
cursor visually but often does **not** generate input/mouse-move events that
games and some UIs require for hover/hit-box checks. Absolute SendInput does.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

# Win32 constants
_MOUSEEVENTF_MOVE = 0x0001
_MOUSEEVENTF_ABSOLUTE = 0x8000
_MOUSEEVENTF_VIRTUALDESK = 0x4000  # multi-monitor absolute coords
_INPUT_MOUSE = 0
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    )


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    )


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class _INPUTUNION(ctypes.Union):
    _fields_ = (("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT))


class _INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("union", _INPUTUNION))


def uses_sendinput() -> bool:
    """True when this process can inject mouse moves via SendInput."""
    return sys.platform == "win32"


def cursor_pos() -> tuple[int, int]:
    """Return current cursor position in virtual-screen pixels."""
    if not uses_sendinput():
        raise RuntimeError("cursor_pos is Windows-only")
    pt = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
        raise OSError("GetCursorPos failed")
    return int(pt.x), int(pt.y)


def move_absolute(x: int, y: int) -> None:
    """Move cursor to global (x, y) using SendInput absolute + virtual desktop."""
    if not uses_sendinput():
        raise RuntimeError("move_absolute is Windows-only")
    user32 = ctypes.windll.user32
    vx = user32.GetSystemMetrics(_SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(_SM_YVIRTUALSCREEN)
    vw = max(1, user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN))
    vh = max(1, user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN))
    # Map pixels → 0..65535 across the virtual desktop.
    abs_x = int(round((int(x) - vx) * 65535 / max(1, vw - 1)))
    abs_y = int(round((int(y) - vy) * 65535 / max(1, vh - 1)))
    abs_x = max(0, min(65535, abs_x))
    abs_y = max(0, min(65535, abs_y))

    inp = _INPUT()
    inp.type = _INPUT_MOUSE
    inp.union.mi = _MOUSEINPUT(
        dx=abs_x,
        dy=abs_y,
        mouseData=0,
        dwFlags=_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE | _MOUSEEVENTF_VIRTUALDESK,
        time=0,
        dwExtraInfo=None,
    )
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
    if sent != 1:
        raise OSError(f"SendInput move failed (sent={sent})")


def move_relative(dx: int, dy: int) -> None:
    """Relative SendInput move in pixels (subject to mouse acceleration)."""
    if not uses_sendinput():
        raise RuntimeError("move_relative is Windows-only")
    if dx == 0 and dy == 0:
        return
    inp = _INPUT()
    inp.type = _INPUT_MOUSE
    inp.union.mi = _MOUSEINPUT(
        dx=int(dx),
        dy=int(dy),
        mouseData=0,
        dwFlags=_MOUSEEVENTF_MOVE,
        time=0,
        dwExtraInfo=None,
    )
    sent = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
    if sent != 1:
        raise OSError(f"SendInput relative move failed (sent={sent})")
