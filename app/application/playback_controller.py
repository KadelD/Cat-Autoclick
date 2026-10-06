"""Qt adapter around MacroPlayer (background thread)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from app.core.control_flow import ControlFlowError, validate_control_flow
from app.core.models import Preset
from app.core.player import MacroPlayer


class PlaybackController(QObject):
    """Play / pause / stop with thread-safe status signals."""

    started = Signal()
    paused = Signal()
    resumed = Signal()
    stopped = Signal()
    status = Signal(str)
    error = Signal(str)
    finished = Signal()
    execution_step_changed = Signal(object)  # int | None — wired when player reports index

    def __init__(self) -> None:
        super().__init__()
        self._player = MacroPlayer(
            on_status=self._on_status_thread,
            on_step=self._on_step_thread,
        )
        self._poll = QTimer(self)
        self._poll.setInterval(200)
        self._poll.timeout.connect(self._poll_player)
        self._was_running = False
        self._execution_step: int | None = None

    def set_execution_step(self, index: int | None) -> None:
        """Update current step highlight for the workflow UI."""
        if self._execution_step == index:
            return
        self._execution_step = index
        self.execution_step_changed.emit(index)

    @property
    def is_running(self) -> bool:
        return self._player.is_running

    @property
    def is_paused(self) -> bool:
        return self._player.is_paused

    def play(self, preset: Preset) -> None:
        """Start playback if preset validates."""
        if self._player.is_running:
            self.status.emit("Already playing")
            return
        if not preset.actions:
            self.error.emit("No actions to play")
            return
        try:
            validate_control_flow(preset.actions)
        except ControlFlowError as exc:
            self.error.emit(f"Control flow error: {exc}")
            return
        self.set_execution_step(None)
        self._player.play(preset)
        self._was_running = True
        self._poll.start()
        self.started.emit()

    def toggle(self, preset: Preset) -> None:
        """Play or stop (matches legacy Ctrl+F8 behavior)."""
        if self._player.is_running:
            self.stop()
        else:
            self.play(preset)

    def pause(self) -> None:
        if not self._player.is_running:
            return
        self._player.pause()
        self.paused.emit()

    def resume(self) -> None:
        if not self._player.is_running:
            return
        self._player.resume()
        self.resumed.emit()

    def toggle_pause(self) -> None:
        if not self._player.is_running:
            return
        self._player.toggle_pause()
        if self._player.is_paused:
            self.paused.emit()
        else:
            self.resumed.emit()

    def stop(self) -> None:
        if self._player.is_running:
            self._player.stop()
        self._poll.stop()
        self.set_execution_step(None)
        self.stopped.emit()

    def _on_status_thread(self, message: str) -> None:
        """Marshal player status from worker thread to Qt."""
        QTimer.singleShot(0, lambda m=message: self._emit_status(m))

    def _on_step_thread(self, index: int | None) -> None:
        """Marshal current step index for workflow highlight."""
        QTimer.singleShot(0, lambda: self.set_execution_step(index))

    def _emit_status(self, message: str) -> None:
        self.status.emit(message)
        if message in ("Finished", "Stopped"):
            self._poll.stop()
            self.finished.emit()
            if message == "Stopped":
                self.stopped.emit()

    def _poll_player(self) -> None:
        """Detect when player thread ends without a final status."""
        if self._was_running and not self._player.is_running:
            self._was_running = False
            self._poll.stop()
            self.finished.emit()
