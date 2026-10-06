"""High-level application mode for toolbar and window behavior."""

from __future__ import annotations

from enum import Enum


class AppState(str, Enum):
    """Single source of truth for idle / record / play / pause / error."""

    IDLE = "idle"
    RECORDING = "recording"
    PLAYING = "playing"
    PAUSED = "paused"
    ERROR = "error"
