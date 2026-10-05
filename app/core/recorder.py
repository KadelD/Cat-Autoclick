"""Record keyboard and mouse input into Action steps."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from pynput import keyboard, mouse
from pynput.mouse import Button

from app.core.models import Action, ActionType, ClickPhase, KeyPhase, MouseButton
from app.core.monitors import to_local

ActionCallback = Callable[[Action], None]
StatusCallback = Callable[[str], None]

BUTTON_MAP = {
    Button.left: MouseButton.LEFT,
    Button.right: MouseButton.RIGHT,
    Button.middle: MouseButton.MIDDLE,
}

# Always-ignored single keys (empty: plain F-keys must remain recordable).
IGNORE_KEY_NAMES: set[str] = set()

_MODS = frozenset({"ctrl", "alt", "shift", "win"})

# Default app hotkey keys (overridden via set_app_hotkeys from settings).
_DEFAULT_APP_CHORDS: list[tuple[frozenset[str], str]] = [
    (frozenset({"ctrl"}), "f6"),
    (frozenset({"ctrl"}), "f7"),
    (frozenset({"ctrl"}), "f8"),
    (frozenset({"ctrl"}), "f9"),
    (frozenset({"ctrl"}), "f10"),
]

# Drag / double-click heuristics.
_MOVE_PX = 10
_CLICK_MS = 350
_DBL_MS = 400
_DBL_PX = 12


@dataclass
class _DownState:
    button: Button
    x: int
    y: int
    at: float
    dragged: bool = False
    last_move_x: int = 0
    last_move_y: int = 0
    last_move_at: float = 0.0


@dataclass
class _PendingClick:
    button: MouseButton
    x: int
    y: int
    at: float
    timer: threading.Timer


def key_to_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    """Normalize a pynput key into a stable string for storage."""
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char
        if key.vk is not None:
            return f"vk_{key.vk}"
        return None
    name = str(key).replace("Key.", "")
    aliases = {
        "ctrl_l": "ctrl",
        "ctrl_r": "ctrl",
        "alt_l": "alt",
        "alt_r": "alt",
        "shift_l": "shift",
        "shift_r": "shift",
        "cmd_l": "win",
        "cmd_r": "win",
        "cmd": "win",
    }
    return aliases.get(name, name)


class MacroRecorder:
    """Capture input events and emit Action objects with inter-event delays."""

    def __init__(
        self,
        on_action: ActionCallback | None = None,
        on_status: StatusCallback | None = None,
    ) -> None:
        self._on_action = on_action or (lambda _a: None)
        self._on_status = on_status or (lambda _m: None)
        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None
        self._recording = False
        self._paused = False
        self._monitor_index = 0
        self._last_event_at: float | None = None
        self._pressed_keys: set[str] = set()
        self._lock = threading.Lock()
        self._ignore_names: set[str] = set(IGNORE_KEY_NAMES)
        self._downs: dict[Button, _DownState] = {}
        self._pending_click: _PendingClick | None = None
        self._awaiting_double: MouseButton | None = None
        self._double_origin: tuple[int, int] | None = None
        self._ctrl_unemitted = False
        self._eating_hotkey = False
        self._app_chords: list[tuple[frozenset[str], str]] = list(_DEFAULT_APP_CHORDS)
        self._app_control_keys: set[str] = {key for _mods, key in self._app_chords}

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_app_hotkeys(self, chords: list[str]) -> None:
        """Register app hotkey chords so those keystrokes are not recorded."""
        from app.core.settings import normalize_hotkey

        parsed: list[tuple[frozenset[str], str]] = []
        for chord in chords:
            raw = normalize_hotkey(chord)
            if not raw:
                continue
            parts = [p for p in raw.split("+") if p]
            mods = frozenset(p for p in parts if p in _MODS)
            keys = [p for p in parts if p not in _MODS]
            if keys:
                parsed.append((mods, keys[-1]))
        self._app_chords = parsed or list(_DEFAULT_APP_CHORDS)
        self._app_control_keys = {key for _mods, key in self._app_chords}

    def set_ignore_hotkeys(self, names: list[str]) -> None:
        """Ignore listed single keys; app chords are handled separately."""
        cleaned: set[str] = set()
        for n in names:
            if not n:
                continue
            low = n.lower().replace(" ", "")
            # Skip chord labels like "ctrl+f9" — those must not block plain F9.
            if "+" in low or low.startswith("ctrl"):
                continue
            if low in self._app_control_keys:
                continue
            cleaned.add(low)
        self._ignore_names = cleaned | set(IGNORE_KEY_NAMES)

    def _held_mods(self) -> set[str]:
        """Modifiers currently considered held (includes deferred Ctrl)."""
        held = {k for k in self._pressed_keys if k in _MODS}
        if self._ctrl_unemitted:
            held.add("ctrl")
        return held

    def _matches_app_hotkey(self, key_low: str) -> bool:
        """True when key_low + held modifiers match a registered app chord."""
        held = self._held_mods()
        for mods, key in self._app_chords:
            if key == key_low and mods == frozenset(held):
                return True
        return False

    def _any_chord_uses_ctrl(self) -> bool:
        return any("ctrl" in mods for mods, _ in self._app_chords)

    def start(self, monitor_index: int = 0) -> None:
        if self._recording:
            return
        self._monitor_index = monitor_index
        self._last_event_at = time.monotonic()
        self._pressed_keys.clear()
        self._downs.clear()
        self._clear_pending_click(emit=False)
        self._awaiting_double = None
        self._double_origin = None
        self._ctrl_unemitted = False
        self._eating_hotkey = False
        self._paused = False
        self._recording = True
        self._mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_move=self._on_move,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()
        self._on_status("Recording…")

    def stop(self) -> None:
        self._recording = False
        self._paused = False
        self._ctrl_unemitted = False
        self._eating_hotkey = False
        self._clear_pending_click(emit=True)
        self._downs.clear()
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        self._on_status("Record stopped")

    def pause(self) -> None:
        """Ignore input until resume (OCR picker / settings dialog)."""
        if not self._recording:
            return
        self._clear_pending_click(emit=True)
        self._downs.clear()
        self._awaiting_double = None
        self._double_origin = None
        self._ctrl_unemitted = False
        self._eating_hotkey = False
        self._paused = True

    def resume(self) -> None:
        """Resume capturing; reset timing so pause duration is not a delay."""
        if not self._recording:
            return
        self._paused = False
        self._last_event_at = time.monotonic()
        self._pressed_keys.clear()
        self._downs.clear()
        self._awaiting_double = None
        self._double_origin = None
        self._ctrl_unemitted = False
        self._eating_hotkey = False

    def _consume_gap_ms(self) -> int:
        now = time.monotonic()
        if self._last_event_at is None:
            self._last_event_at = now
            return 0
        gap = int((now - self._last_event_at) * 1000)
        self._last_event_at = now
        return max(0, min(gap, 60_000))

    def _emit(self, action: Action) -> None:
        gap = self._consume_gap_ms()
        if gap >= 15:
            self._on_action(Action(type=ActionType.DELAY, delay_ms=gap))
        self._on_action(action)

    def _local(self, x: int, y: int) -> tuple[int, int]:
        return to_local(self._monitor_index, int(x), int(y))

    def _clear_pending_click(self, emit: bool) -> None:
        pending = self._pending_click
        self._pending_click = None
        if pending is None:
            return
        try:
            pending.timer.cancel()
        except Exception:
            pass
        if emit:
            self._emit(
                Action(
                    type=ActionType.MOUSE_CLICK,
                    x=pending.x,
                    y=pending.y,
                    button=pending.button,
                    click_phase=ClickPhase.CLICK,
                    click_count=1,
                )
            )

    def _flush_pending_as_single(self) -> None:
        """Timer callback: promote buffered click to a single click."""
        with self._lock:
            pending = self._pending_click
            if pending is None:
                return
            self._pending_click = None
        self._emit(
            Action(
                type=ActionType.MOUSE_CLICK,
                x=pending.x,
                y=pending.y,
                button=pending.button,
                click_phase=ClickPhase.CLICK,
                click_count=1,
            )
        )

    def _on_move(self, x: int, y: int) -> None:
        """Track drag end point only — no per-move samples (avoids stuttery macros)."""
        if not self._recording or self._paused or not self._downs:
            return
        lx, ly = self._local(x, y)
        for state in list(self._downs.values()):
            dx = abs(lx - state.x)
            dy = abs(ly - state.y)
            if not state.dragged:
                if dx < _MOVE_PX and dy < _MOVE_PX:
                    continue
                self._clear_pending_click(emit=True)
                self._awaiting_double = None
                self._double_origin = None
                state.dragged = True
            state.last_move_x = lx
            state.last_move_y = ly

    def _on_click(self, x: int, y: int, button: Button, pressed: bool) -> None:
        if not self._recording or self._paused:
            return
        mapped = BUTTON_MAP.get(button)
        if mapped is None:
            return
        lx, ly = self._local(x, y)
        now = time.monotonic()

        if pressed:
            # Second down of a double-click: wait for matching up.
            pending = self._pending_click
            if (
                pending is not None
                and pending.button == mapped
                and (now - pending.at) * 1000 <= _DBL_MS
                and abs(lx - pending.x) <= _DBL_PX
                and abs(ly - pending.y) <= _DBL_PX
            ):
                try:
                    pending.timer.cancel()
                except Exception:
                    pass
                origin = (pending.x, pending.y)
                self._pending_click = None
                self._awaiting_double = mapped
                self._double_origin = origin
                self._downs[button] = _DownState(button=button, x=lx, y=ly, at=now)
                return

            self._clear_pending_click(emit=True)
            self._awaiting_double = None
            self._double_origin = None
            self._downs[button] = _DownState(button=button, x=lx, y=ly, at=now)
            return

        # Release
        state = self._downs.pop(button, None)
        if state is None:
            return

        if state.dragged:
            # One drag step: start → end over total press duration (constant speed on play).
            duration = max(1, int((now - state.at) * 1000))
            self._emit(
                Action(
                    type=ActionType.MOUSE_DRAG,
                    x=state.x,
                    y=state.y,
                    end_x=lx,
                    end_y=ly,
                    button=mapped,
                    hold_ms=duration,
                    delay_ms=0,
                )
            )
            return

        # Completing second half of double-click.
        if self._awaiting_double == mapped:
            self._awaiting_double = None
            origin = self._double_origin or (state.x, state.y)
            self._double_origin = None
            hold_ms = (now - state.at) * 1000
            if hold_ms <= _CLICK_MS:
                self._emit(
                    Action(
                        type=ActionType.MOUSE_CLICK,
                        x=origin[0],
                        y=origin[1],
                        button=mapped,
                        click_phase=ClickPhase.CLICK,
                        click_count=2,
                    )
                )
                return
            self._emit(
                Action(
                    type=ActionType.MOUSE_CLICK,
                    x=state.x,
                    y=state.y,
                    button=mapped,
                    click_phase=ClickPhase.DOWN,
                )
            )
            self._emit(
                Action(
                    type=ActionType.MOUSE_CLICK,
                    x=lx,
                    y=ly,
                    button=mapped,
                    click_phase=ClickPhase.UP,
                )
            )
            return

        hold_ms = (now - state.at) * 1000
        if hold_ms <= _CLICK_MS:
            # Buffer as a click candidate for possible double-click.
            self._clear_pending_click(emit=True)
            timer = threading.Timer(_DBL_MS / 1000.0, self._flush_pending_as_single)
            timer.daemon = True
            self._pending_click = _PendingClick(
                button=mapped, x=state.x, y=state.y, at=now, timer=timer
            )
            timer.start()
            return

        # Long press without drag path: record down/up.
        self._emit(
            Action(
                type=ActionType.MOUSE_CLICK,
                x=state.x,
                y=state.y,
                button=mapped,
                click_phase=ClickPhase.DOWN,
            )
        )
        self._emit(
            Action(
                type=ActionType.MOUSE_CLICK,
                x=lx,
                y=ly,
                button=mapped,
                click_phase=ClickPhase.UP,
            )
        )

    def _flush_deferred_ctrl(self) -> None:
        """Emit a buffered Ctrl-down once another (non-hotkey) key arrives."""
        if not self._ctrl_unemitted:
            return
        self._ctrl_unemitted = False
        self._emit(Action(type=ActionType.KEY, key="ctrl", key_phase=KeyPhase.DOWN))

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if not self._recording or self._paused:
            return
        name = key_to_name(key)
        if not name:
            return
        low = name.lower()
        if low in self._ignore_names:
            return

        # App hotkey chords: do not record the chord.
        if low in self._app_control_keys and self._matches_app_hotkey(low):
            self._ctrl_unemitted = False
            self._eating_hotkey = True
            return

        with self._lock:
            if name in self._pressed_keys:
                return
            self._pressed_keys.add(name)

        if low == "ctrl" and self._any_chord_uses_ctrl():
            # Defer Ctrl-down until we know it is not part of an app chord.
            self._ctrl_unemitted = True
            self._eating_hotkey = False
            return

        self._clear_pending_click(emit=True)
        self._flush_deferred_ctrl()
        self._emit(Action(type=ActionType.KEY, key=name, key_phase=KeyPhase.DOWN))

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if not self._recording or self._paused:
            return
        name = key_to_name(key)
        if not name:
            return
        low = name.lower()
        if low in self._ignore_names:
            return

        if low in self._app_control_keys and self._eating_hotkey:
            return

        with self._lock:
            was_pressed = name in self._pressed_keys
            self._pressed_keys.discard(name)

        if low == "ctrl":
            if self._ctrl_unemitted:
                # Bare Ctrl tap — record down+up.
                self._ctrl_unemitted = False
                self._clear_pending_click(emit=True)
                self._emit(Action(type=ActionType.KEY, key="ctrl", key_phase=KeyPhase.DOWN))
                self._emit(Action(type=ActionType.KEY, key="ctrl", key_phase=KeyPhase.UP))
                return
            if self._eating_hotkey:
                self._eating_hotkey = False
                return
            if not was_pressed:
                return
            self._emit(Action(type=ActionType.KEY, key="ctrl", key_phase=KeyPhase.UP))
            return

        if not was_pressed:
            return
        self._emit(Action(type=ActionType.KEY, key=name, key_phase=KeyPhase.UP))
