"""Central app state and coordination between UI and core controllers."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from app.application.app_state import AppState
from app.application.hotkey_service import HotkeyService
from app.application.macro_controller import MacroController
from app.application.playback_controller import PlaybackController
from app.application.recording_controller import RecordingController
from app.core.settings import AppSettings, get_settings, load_settings, save_settings


class AppController(QObject):
    """Owns macro/record/play controllers and application state."""

    state_changed = Signal(object)
    settings_changed = Signal(object)
    status_message = Signal(str)
    error_message = Signal(str)
    ocr_full_requested = Signal()
    ocr_area_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._state = AppState.IDLE
        self._settings = load_settings()
        self.macros = MacroController()
        self.playback = PlaybackController()
        self.recording = RecordingController()
        self.hotkeys = HotkeyService()

        self.macros.status_message.connect(self.status_message.emit)
        self.playback.status.connect(self.status_message.emit)
        self.playback.error.connect(self.error_message.emit)
        self.recording.status.connect(self.status_message.emit)

        self.playback.started.connect(lambda: self._set_state(AppState.PLAYING))
        self.playback.paused.connect(lambda: self._set_state(AppState.PAUSED))
        self.playback.resumed.connect(lambda: self._set_state(AppState.PLAYING))
        self.playback.stopped.connect(lambda: self._set_state(AppState.IDLE))
        self.playback.finished.connect(lambda: self._set_state(AppState.IDLE))

        self.recording.started.connect(lambda: self._set_state(AppState.RECORDING))
        self.recording.stopped.connect(lambda: self._set_state(AppState.IDLE))

        self.recording.action_captured.connect(self.macros.append_action)
        self.settings_changed.connect(lambda _s: self.recording.apply_settings(self._settings))

    @property
    def state(self) -> AppState:
        return self._state

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def initialize(self) -> None:
        """Load settings and register global hotkeys."""
        self.recording.apply_settings(self._settings)
        self._bind_hotkeys()

    def _bind_hotkeys(self) -> None:
        def _sched(fn):
            QTimer.singleShot(0, fn)

        try:
            self.hotkeys.set_handlers(
                {
                    "play": self.toggle_play,
                    "record": self.toggle_record,
                    "stop": self.stop_all,
                    "ocr_full": self._hotkey_ocr_full,
                    "ocr_area": self._hotkey_ocr_area,
                }
            )
            self.hotkeys.apply(self._settings, _sched)
        except RuntimeError as exc:
            self.error_message.emit(str(exc))

    def apply_settings(self, settings: AppSettings) -> None:
        """Persist and propagate settings."""
        save_settings(settings)
        self._settings = get_settings()
        self.recording.apply_settings(self._settings)
        self._bind_hotkeys()
        self.settings_changed.emit(self._settings)

    def toggle_play(self) -> None:
        preset = self.macros.current
        if preset is None:
            self.error_message.emit("No preset selected")
            return
        if self.recording.is_recording:
            self.recording.stop()
        self.playback.toggle(preset)

    def toggle_record(self) -> None:
        preset = self.macros.current
        if preset is None:
            self.error_message.emit("Create a preset first")
            return
        if self.playback.is_running:
            self.playback.stop()
        mon = preset.monitor_index
        self.recording.toggle(mon)

    def stop_all(self) -> None:
        if self.recording.is_recording:
            self.recording.stop()
        if self.playback.is_running:
            self.playback.stop()
        self._set_state(AppState.IDLE)
        self.status_message.emit("Stopped")

    def shutdown(self) -> None:
        self.stop_all()
        self.hotkeys.stop()

    def _set_state(self, state: AppState) -> None:
        if self._state == state:
            return
        self._state = state
        self.state_changed.emit(state)

    def _hotkey_ocr_full(self) -> None:
        """Global hotkey: OCR on full monitor (while recording)."""
        if not self._settings.ocr_enabled:
            self.status_message.emit("OCR is disabled in Settings")
            return
        if not self.recording.is_recording:
            self.status_message.emit("Start recording first")
            return
        self.ocr_full_requested.emit()

    def _hotkey_ocr_area(self) -> None:
        """Global hotkey: OCR on dragged region (while recording)."""
        if not self._settings.ocr_enabled:
            self.status_message.emit("OCR is disabled in Settings")
            return
        if not self.recording.is_recording:
            self.status_message.emit("Start recording first")
            return
        self.ocr_area_requested.emit()
