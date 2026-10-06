"""Qt adapter around MacroRecorder with batched action delivery."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from app.core.models import Action
from app.core.recorder import MacroRecorder
from app.core.settings import AppSettings, get_settings


class RecordingController(QObject):
    """Start/stop recording; emits captured actions on the GUI thread."""

    started = Signal()
    stopped = Signal()
    action_captured = Signal(object)
    status = Signal(str)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._recorder = MacroRecorder(
            on_action=self._on_action_thread,
            on_status=self._on_status_thread,
        )
        self._pending: list[Action] = []
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.timeout.connect(self._flush_pending)

    @property
    def is_recording(self) -> bool:
        return self._recorder.is_recording

    @property
    def is_paused(self) -> bool:
        return self._recorder.is_paused

    def apply_settings(self, settings: AppSettings) -> None:
        """Sync recorder swallow list with app hotkeys."""
        chords = list(settings.hotkey_map().values())
        if not settings.ocr_enabled:
            chords = [
                settings.hotkey_map()["play"],
                settings.hotkey_map()["record"],
                settings.hotkey_map()["stop"],
            ]
        self._recorder.set_app_hotkeys(chords)
        self._recorder.set_ignore_hotkeys([])

    def start(self, monitor_index: int) -> None:
        if self._recorder.is_recording:
            return
        self.apply_settings(get_settings())
        self._recorder.start(monitor_index)
        self.started.emit()

    def stop(self) -> None:
        if self._recorder.is_recording:
            self._recorder.stop()
        self._flush_pending()
        self.stopped.emit()

    def toggle(self, monitor_index: int) -> None:
        if self._recorder.is_recording:
            self.stop()
        else:
            self.start(monitor_index)

    def pause(self) -> None:
        self._recorder.pause()

    def resume(self) -> None:
        self._recorder.resume()

    def _on_action_thread(self, action: Action) -> None:
        self._pending.append(action)
        if not self._flush_timer.isActive():
            self._flush_timer.start(16)

    def _flush_pending(self) -> None:
        batch = self._pending
        self._pending = []
        for action in batch:
            self.action_captured.emit(action)

    def _on_status_thread(self, message: str) -> None:
        QTimer.singleShot(0, lambda m=message: self.status.emit(m))
