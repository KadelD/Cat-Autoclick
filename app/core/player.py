"""Play back a list of macro actions on a background thread."""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from typing import Any

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key
from pynput.mouse import Button
from pynput.mouse import Controller as MouseController

from app.core.models import Action, ActionType, ClickPhase, KeyPhase, MouseButton, Preset
from app.core.monitors import to_global

StatusCallback = Callable[[str], None]


# Map friendly key names to pynput Key members.
SPECIAL_KEYS: dict[str, Any] = {
    "ctrl": Key.ctrl,
    "ctrl_l": Key.ctrl_l,
    "ctrl_r": Key.ctrl_r,
    "alt": Key.alt,
    "alt_l": Key.alt_l,
    "alt_r": Key.alt_gr if hasattr(Key, "alt_gr") else Key.alt_r,
    "alt_gr": Key.alt_gr if hasattr(Key, "alt_gr") else Key.alt_r,
    "shift": Key.shift,
    "shift_l": Key.shift_l,
    "shift_r": Key.shift_r,
    "cmd": Key.cmd,
    "win": Key.cmd,
    "super": Key.cmd,
    "enter": Key.enter,
    "return": Key.enter,
    "tab": Key.tab,
    "esc": Key.esc,
    "escape": Key.esc,
    "space": Key.space,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "insert": Key.insert,
    "home": Key.home,
    "end": Key.end,
    "page_up": Key.page_up,
    "page_down": Key.page_down,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "caps_lock": Key.caps_lock,
    "print_screen": Key.print_screen,
    "scroll_lock": Key.scroll_lock,
    "pause": Key.pause,
    "menu": Key.menu,
    **{f"f{i}": getattr(Key, f"f{i}") for i in range(1, 25)},
}

MOUSE_BUTTONS = {
    MouseButton.LEFT: Button.left,
    MouseButton.RIGHT: Button.right,
    MouseButton.MIDDLE: Button.middle,
}


def resolve_key(name: str) -> Any:
    """Convert a stored key string into a pynput key token."""
    if not name:
        raise ValueError("Empty key name")
    lowered = name.lower()
    if lowered in SPECIAL_KEYS:
        return SPECIAL_KEYS[lowered]
    if len(name) == 1:
        return name
    # Fallback: try attribute on Key
    attr = getattr(Key, lowered, None)
    if attr is not None:
        return attr
    return name


class MacroPlayer:
    """Execute preset actions with stop/pause support."""

    def __init__(self, on_status: StatusCallback | None = None) -> None:
        self._on_status = on_status or (lambda _msg: None)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.set()  # not paused
        self._mouse = MouseController()
        self._keyboard = KeyboardController()
        self._held_keys: list[Any] = []
        self._held_buttons: list[Button] = []
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def play(self, preset: Preset) -> None:
        """Start playback of the given preset on a worker thread."""
        if self.is_running:
            self._on_status("Already playing")
            return
        if not preset.actions:
            self._on_status("No actions to play")
            return
        self._stop.clear()
        self._pause.set()
        self._thread = threading.Thread(target=self._run, args=(preset,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Request stop and release any held inputs."""
        self._stop.set()
        self._pause.set()
        self._release_all()
        self._on_status("Stopped")

    def pause(self) -> None:
        self._pause.clear()
        self._on_status("Paused")

    def resume(self) -> None:
        self._pause.set()
        self._on_status("Playing…")

    def toggle_pause(self) -> None:
        if self._pause.is_set():
            self.pause()
        else:
            self.resume()

    def _wait_interruptible(self, seconds: float) -> bool:
        """Sleep in small slices; return False if stop was requested."""
        end = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end:
            if self._stop.is_set():
                return False
            self._pause.wait(0.05)
            if self._stop.is_set():
                return False
            remaining = end - time.monotonic()
            time.sleep(min(0.05, max(0.0, remaining)))
        return not self._stop.is_set()

    def _run(self, preset: Preset) -> None:
        self._on_status("Playing…")
        loops = preset.loop_count
        infinite = loops == 0
        round_no = 0
        try:
            while infinite or round_no < loops:
                if self._stop.is_set():
                    break
                round_no += 1
                self._on_status(f"Playing round {round_no}" + (" (∞)" if infinite else f"/{loops}"))
                for action in preset.actions:
                    if self._stop.is_set():
                        break
                    self._pause.wait()
                    if self._stop.is_set():
                        break
                    self._execute(action, preset.monitor_index)
                    wait_ms = action.after_ms
                    if wait_ms <= 0 and action.type != ActionType.DELAY:
                        wait_ms = action.delay_ms
                    if preset.jitter_ms > 0 and action.type != ActionType.DELAY:
                        wait_ms += random.randint(0, preset.jitter_ms)
                    if not self._wait_interruptible(wait_ms / 1000.0):
                        break
        finally:
            self._release_all()
            if self._stop.is_set():
                self._on_status("Stopped")
            else:
                self._on_status("Finished")

    def _execute(self, action: Action, monitor_index: int) -> None:
        if action.type == ActionType.DELAY:
            if action.delay_min_ms is not None and action.delay_max_ms is not None:
                low = min(action.delay_min_ms, action.delay_max_ms)
                high = max(action.delay_min_ms, action.delay_max_ms)
                ms = random.randint(low, high)
            else:
                ms = action.delay_ms
            self._wait_interruptible(ms / 1000.0)
            return

        if action.type == ActionType.MOUSE_MOVE:
            gx, gy = to_global(monitor_index, int(action.x or 0), int(action.y or 0))
            self._mouse.position = (gx, gy)
            return

        if action.type == ActionType.MOUSE_CLICK:
            gx, gy = to_global(monitor_index, int(action.x or 0), int(action.y or 0))
            self._mouse.position = (gx, gy)
            btn = MOUSE_BUTTONS[action.button or MouseButton.LEFT]
            if action.click_phase == ClickPhase.DOWN:
                self._mouse.press(btn)
                self._track_button(btn, pressed=True)
            elif action.click_phase == ClickPhase.UP:
                self._mouse.release(btn)
                self._track_button(btn, pressed=False)
            else:
                self._mouse.click(btn, 1)
            return

        if action.type == ActionType.KEY:
            token = resolve_key(action.key or "")
            if action.key_phase == KeyPhase.DOWN:
                self._keyboard.press(token)
                self._track_key(token, pressed=True)
            elif action.key_phase == KeyPhase.UP:
                self._keyboard.release(token)
                self._track_key(token, pressed=False)
            else:
                self._keyboard.press(token)
                self._keyboard.release(token)
            return

        if action.type == ActionType.HOTKEY:
            tokens = [resolve_key(k) for k in action.keys]
            for t in tokens:
                self._keyboard.press(t)
            for t in reversed(tokens):
                self._keyboard.release(t)
            return

        if action.type == ActionType.HOLD:
            if action.key:
                token = resolve_key(action.key)
                self._keyboard.press(token)
                self._track_key(token, pressed=True)
                self._wait_interruptible(action.hold_ms / 1000.0)
                self._keyboard.release(token)
                self._track_key(token, pressed=False)
            else:
                btn = MOUSE_BUTTONS[action.button or MouseButton.LEFT]
                if action.x is not None and action.y is not None:
                    gx, gy = to_global(monitor_index, int(action.x), int(action.y))
                    self._mouse.position = (gx, gy)
                self._mouse.press(btn)
                self._track_button(btn, pressed=True)
                self._wait_interruptible(action.hold_ms / 1000.0)
                self._mouse.release(btn)
                self._track_button(btn, pressed=False)

    def _track_key(self, token: Any, pressed: bool) -> None:
        with self._lock:
            if pressed:
                if token not in self._held_keys:
                    self._held_keys.append(token)
            elif token in self._held_keys:
                self._held_keys.remove(token)

    def _track_button(self, btn: Button, pressed: bool) -> None:
        with self._lock:
            if pressed:
                if btn not in self._held_buttons:
                    self._held_buttons.append(btn)
            elif btn in self._held_buttons:
                self._held_buttons.remove(btn)

    def _release_all(self) -> None:
        with self._lock:
            keys = list(self._held_keys)
            buttons = list(self._held_buttons)
            self._held_keys.clear()
            self._held_buttons.clear()
        for token in keys:
            try:
                self._keyboard.release(token)
            except Exception:
                pass
        for btn in buttons:
            try:
                self._mouse.release(btn)
            except Exception:
                pass
