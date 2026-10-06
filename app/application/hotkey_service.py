"""Global hotkeys (pynput) with callbacks on the Qt main thread."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from pynput import keyboard

from app.core.settings import AppSettings


class HotkeyService:
    """Bind/unbind GlobalHotKeys from AppSettings."""

    def __init__(self) -> None:
        self._listener: keyboard.GlobalHotKeys | None = None
        self._handlers: dict[str, Callable[[], None]] = {}

    def set_handlers(self, handlers: dict[str, Callable[[], None]]) -> None:
        """Logical action name → callable (play, record, stop, ocr_full, ocr_area)."""
        self._handlers = handlers

    def apply(self, settings: AppSettings, schedule: Callable[[Callable[[], None]], None]) -> None:
        """Rebuild hotkeys; schedule runs fn on GUI thread (e.g. lambda fn: QTimer.singleShot(0, fn))."""
        self.stop()
        actions = {
            "play": self._handlers.get("play"),
            "record": self._handlers.get("record"),
            "stop": self._handlers.get("stop"),
            "ocr_full": self._handlers.get("ocr_full"),
            "ocr_area": self._handlers.get("ocr_area"),
        }
        mapping: dict[str, object] = {}
        for pattern, name in settings.pynput_hotkeys().items():
            if name.startswith("ocr_") and not settings.ocr_enabled:
                continue
            handler = actions.get(name)
            if handler is None:
                continue
            mapping[pattern] = lambda h=handler: schedule(h)
        try:
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.start()
        except Exception as exc:
            raise RuntimeError(f"Hotkeys unavailable: {exc}") from exc

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
