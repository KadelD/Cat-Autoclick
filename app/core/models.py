"""Preset and action data models for Cat Autoclick."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class ActionType(str, Enum):
    """Supported macro step kinds."""

    MOUSE_CLICK = "mouse_click"
    MOUSE_MOVE = "mouse_move"
    KEY = "key"
    HOTKEY = "hotkey"
    HOLD = "hold"
    DELAY = "delay"


class MouseButton(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class KeyPhase(str, Enum):
    TAP = "tap"
    DOWN = "down"
    UP = "up"


class ClickPhase(str, Enum):
    CLICK = "click"
    DOWN = "down"
    UP = "up"


@dataclass
class Action:
    """Single macro step."""

    type: ActionType
    id: str = field(default_factory=lambda: uuid4().hex[:10])
    # Mouse
    x: int | None = None
    y: int | None = None
    button: MouseButton | None = None
    click_phase: ClickPhase = ClickPhase.CLICK
    # Keyboard
    key: str | None = None
    keys: list[str] = field(default_factory=list)
    key_phase: KeyPhase = KeyPhase.TAP
    # Timing
    hold_ms: int = 0
    delay_ms: int = 50
    delay_min_ms: int | None = None
    delay_max_ms: int | None = None
    # Extra pause after this step (used by recorder for inter-event gaps)
    after_ms: int = 0

    def summary(self) -> str:
        """Human-readable one-line description for the action list."""
        if self.type == ActionType.MOUSE_CLICK:
            btn = (self.button or MouseButton.LEFT).value
            phase = self.click_phase.value
            return f"Mouse {btn} {phase} @ ({self.x}, {self.y})"
        if self.type == ActionType.MOUSE_MOVE:
            return f"Move cursor to ({self.x}, {self.y})"
        if self.type == ActionType.KEY:
            return f"Key {self.key_phase.value}: {self.key}"
        if self.type == ActionType.HOTKEY:
            return f"Hotkey: {'+'.join(self.keys)}"
        if self.type == ActionType.HOLD:
            target = self.key or f"mouse {(self.button or MouseButton.LEFT).value}"
            return f"Hold {target} for {self.hold_ms} ms"
        if self.type == ActionType.DELAY:
            if self.delay_min_ms is not None and self.delay_max_ms is not None:
                return f"Delay {self.delay_min_ms}-{self.delay_max_ms} ms"
            return f"Delay {self.delay_ms} ms"
        return self.type.value

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        if self.button is not None:
            data["button"] = self.button.value
        else:
            data["button"] = None
        data["click_phase"] = self.click_phase.value
        data["key_phase"] = self.key_phase.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Action:
        button = data.get("button")
        return cls(
            id=data.get("id") or uuid4().hex[:10],
            type=ActionType(data["type"]),
            x=data.get("x"),
            y=data.get("y"),
            button=MouseButton(button) if button else None,
            click_phase=ClickPhase(data.get("click_phase", "click")),
            key=data.get("key"),
            keys=list(data.get("keys") or []),
            key_phase=KeyPhase(data.get("key_phase", "tap")),
            hold_ms=int(data.get("hold_ms") or 0),
            delay_ms=int(data.get("delay_ms") or 50),
            delay_min_ms=data.get("delay_min_ms"),
            delay_max_ms=data.get("delay_max_ms"),
            after_ms=int(data.get("after_ms") or 0),
        )


@dataclass
class Preset:
    """Named macro with monitor target and playback settings."""

    name: str
    id: str = field(default_factory=lambda: uuid4().hex[:10])
    monitor_index: int = 0
    actions: list[Action] = field(default_factory=list)
    loop_count: int = 1  # 0 = infinite
    jitter_ms: int = 10
    play_hotkey: str = "F8"
    record_hotkey: str = "F9"
    stop_hotkey: str = "F10"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "monitor_index": self.monitor_index,
            "loop_count": self.loop_count,
            "jitter_ms": self.jitter_ms,
            "play_hotkey": self.play_hotkey,
            "record_hotkey": self.record_hotkey,
            "stop_hotkey": self.stop_hotkey,
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Preset:
        return cls(
            id=data.get("id") or uuid4().hex[:10],
            name=data.get("name") or "Untitled",
            monitor_index=int(data.get("monitor_index") or 0),
            loop_count=int(data.get("loop_count") if data.get("loop_count") is not None else 1),
            jitter_ms=int(data.get("jitter_ms") if data.get("jitter_ms") is not None else 10),
            play_hotkey=data.get("play_hotkey") or "F8",
            record_hotkey=data.get("record_hotkey") or "F9",
            stop_hotkey=data.get("stop_hotkey") or "F10",
            actions=[Action.from_dict(a) for a in data.get("actions") or []],
        )
