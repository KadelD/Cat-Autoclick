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
    MOUSE_DRAG = "mouse_drag"
    KEY = "key"
    HOTKEY = "hotkey"
    HOLD = "hold"
    DELAY = "delay"
    FIND_TEXT = "find_text"
    FIND_IMAGE = "find_image"
    WAIT_TEXT = "wait_text"
    WAIT_IMAGE = "wait_image"
    IF_TEXT = "if_text"
    IF_IMAGE = "if_image"
    ELSE = "else"
    ENDIF = "endif"


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


class OnFail(str, Enum):
    STOP = "stop"
    CONTINUE = "continue"


@dataclass
class Action:
    """Single macro step."""

    type: ActionType
    id: str = field(default_factory=lambda: uuid4().hex[:10])
    # Mouse
    x: int | None = None
    y: int | None = None
    end_x: int | None = None
    end_y: int | None = None
    button: MouseButton | None = None
    click_phase: ClickPhase = ClickPhase.CLICK
    click_count: int = 1
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
    # Vision / control flow
    query: str = ""
    image_path: str = ""
    threshold: float = 0.85
    timeout_ms: int = 5000
    on_fail: OnFail = OnFail.STOP
    # Capture scope: None = use preset monitor; region w/h 0 = full monitor
    capture_monitor: int | None = None
    region_x: int = 0
    region_y: int = 0
    region_w: int = 0
    region_h: int = 0

    def capture_summary(self) -> str:
        """Short suffix describing capture monitor/region when not full default."""
        parts: list[str] = []
        if self.capture_monitor is not None:
            parts.append(f"mon{self.capture_monitor}")
        if self.region_w > 0 and self.region_h > 0:
            parts.append(f"{self.region_x},{self.region_y} {self.region_w}x{self.region_h}")
        return f" [{', '.join(parts)}]" if parts else ""

    def summary(self) -> str:
        """Human-readable one-line description for the action list."""
        if self.type == ActionType.MOUSE_CLICK:
            btn = (self.button or MouseButton.LEFT).value
            if self.click_phase == ClickPhase.DOWN:
                return f"↓ {btn} ({self.x}, {self.y})"
            if self.click_phase == ClickPhase.UP:
                return f"↑ {btn} ({self.x}, {self.y})"
            if self.click_count > 1:
                return f"🖱 {btn} x{self.click_count} ({self.x}, {self.y})"
            return f"🖱 {btn} ({self.x}, {self.y})"
        if self.type == ActionType.MOUSE_MOVE:
            return f"Move cursor to ({self.x}, {self.y})"
        if self.type == ActionType.MOUSE_DRAG:
            btn = (self.button or MouseButton.LEFT).value
            return (
                f"Drag {btn} ({self.x}, {self.y}) → ({self.end_x}, {self.end_y}) "
                f"in {self.hold_ms} ms"
            )
        if self.type == ActionType.KEY:
            key = self.key or "?"
            if self.key_phase == KeyPhase.DOWN:
                return f"↓ {key}"
            if self.key_phase == KeyPhase.UP:
                return f"↑ {key}"
            return key
        if self.type == ActionType.HOTKEY:
            return f"Hotkey: {'+'.join(self.keys)}"
        if self.type == ActionType.HOLD:
            target = self.key or f"mouse {(self.button or MouseButton.LEFT).value}"
            return f"Hold {target} for {self.hold_ms} ms"
        if self.type == ActionType.DELAY:
            if self.delay_min_ms is not None and self.delay_max_ms is not None:
                return f"Delay {self.delay_min_ms}-{self.delay_max_ms} ms"
            return f"Delay {self.delay_ms} ms"
        if self.type == ActionType.FIND_TEXT:
            return f'Find text "{self.query}" then click{self.capture_summary()}'
        if self.type == ActionType.FIND_IMAGE:
            return f'Find image "{self.image_path}" then click{self.capture_summary()}'
        if self.type == ActionType.WAIT_TEXT:
            return f'Wait text "{self.query}" ({self.timeout_ms} ms){self.capture_summary()}'
        if self.type == ActionType.WAIT_IMAGE:
            return f'Wait image "{self.image_path}" ({self.timeout_ms} ms){self.capture_summary()}'
        if self.type == ActionType.IF_TEXT:
            return f'If text "{self.query}"{self.capture_summary()}'
        if self.type == ActionType.IF_IMAGE:
            return f'If image "{self.image_path}"{self.capture_summary()}'
        if self.type == ActionType.ELSE:
            return "Else"
        if self.type == ActionType.ENDIF:
            return "End if"
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
        data["on_fail"] = self.on_fail.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Action:
        button = data.get("button")
        on_fail = data.get("on_fail") or OnFail.STOP.value
        return cls(
            id=data.get("id") or uuid4().hex[:10],
            type=ActionType(data["type"]),
            x=data.get("x"),
            y=data.get("y"),
            end_x=data.get("end_x"),
            end_y=data.get("end_y"),
            button=MouseButton(button) if button else None,
            click_phase=ClickPhase(data.get("click_phase", "click")),
            click_count=max(1, int(data.get("click_count") or 1)),
            key=data.get("key"),
            keys=list(data.get("keys") or []),
            key_phase=KeyPhase(data.get("key_phase", "tap")),
            hold_ms=int(data.get("hold_ms") or 0),
            delay_ms=int(data.get("delay_ms") or 50),
            delay_min_ms=data.get("delay_min_ms"),
            delay_max_ms=data.get("delay_max_ms"),
            after_ms=int(data.get("after_ms") or 0),
            query=str(data.get("query") or ""),
            image_path=str(data.get("image_path") or ""),
            threshold=float(data.get("threshold") if data.get("threshold") is not None else 0.85),
            timeout_ms=int(data.get("timeout_ms") if data.get("timeout_ms") is not None else 5000),
            on_fail=OnFail(on_fail),
            capture_monitor=data.get("capture_monitor"),
            region_x=int(data.get("region_x") or 0),
            region_y=int(data.get("region_y") or 0),
            region_w=int(data.get("region_w") or 0),
            region_h=int(data.get("region_h") or 0),
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
    play_hotkey: str = "Ctrl+F8"
    record_hotkey: str = "Ctrl+F9"
    stop_hotkey: str = "Ctrl+F10"

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
            play_hotkey=data.get("play_hotkey") or "Ctrl+F8",
            record_hotkey=data.get("record_hotkey") or "Ctrl+F9",
            stop_hotkey=data.get("stop_hotkey") or "Ctrl+F10",
            actions=[Action.from_dict(a) for a in data.get("actions") or []],
        )
