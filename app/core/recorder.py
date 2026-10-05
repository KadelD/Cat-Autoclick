"""Record keyboard and mouse input into Action steps."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from pynput import keyboard, mouse
from pynput.keyboard import Key
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

# Keys that should not be recorded (app control hotkeys are filtered by name too).
IGNORE_KEY_NAMES = {"f8", "f9", "f10"}


def key_to_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    """Normalize a pynput key into a stable string for storage."""
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char
        if key.vk is not None:
            # Best-effort for special OEM keys without char.
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
        self._monitor_index = 0
        self._last_event_at: float | None = None
        self._pressed_keys: set[str] = set()
        self._lock = threading.Lock()
        self._ignore_names: set[str] = set(IGNORE_KEY_NAMES)

    @property
    def is_recording(self) -> bool:
        return self._recording

    def set_ignore_hotkeys(self, names: list[str]) -> None:
        """Ignore control hotkeys so they are not stored as macro steps."""
        self._ignore_names = {n.lower() for n in names if n} | set(IGNORE_KEY_NAMES)

    def start(self, monitor_index: int = 0) -> None:
        if self._recording:
            return
        self._monitor_index = monitor_index
        self._last_event_at = time.monotonic()
        self._pressed_keys.clear()
        self._recording = True
        self._mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_move=None,
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
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        self._on_status("Record stopped")

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
        # Attach timing to the previous conceptual gap as after_ms on this action
        # by also emitting a delay when the gap is meaningful.
        if gap >= 15:
            delay = Action(type=ActionType.DELAY, delay_ms=gap)
            self._on_action(delay)
        self._on_action(action)

    def _on_click(self, x: int, y: int, button: Button, pressed: bool) -> None:
        if not self._recording:
            return
        mapped = BUTTON_MAP.get(button)
        if mapped is None:
            return
        lx, ly = to_local(self._monitor_index, int(x), int(y))
        phase = ClickPhase.DOWN if pressed else ClickPhase.UP
        # Collapse quick down+up into a single click for cleaner macros:
        # we still record down/up separately so hold/drag works; UI can merge later.
        action = Action(
            type=ActionType.MOUSE_CLICK,
            x=lx,
            y=ly,
            button=mapped,
            click_phase=phase,
        )
        self._emit(action)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if not self._recording:
            return
        name = key_to_name(key)
        if not name or name.lower() in self._ignore_names:
            return
        with self._lock:
            if name in self._pressed_keys:
                return  # key repeat
            self._pressed_keys.add(name)
        self._emit(
            Action(type=ActionType.KEY, key=name, key_phase=KeyPhase.DOWN)
        )

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if not self._recording:
            return
        name = key_to_name(key)
        if not name or name.lower() in self._ignore_names:
            return
        with self._lock:
            self._pressed_keys.discard(name)
        self._emit(
            Action(type=ActionType.KEY, key=name, key_phase=KeyPhase.UP)
        )
