"""Play back a list of macro actions on a background thread."""

from __future__ import annotations

import math
import random
import threading
import time
from collections.abc import Callable
from typing import Any

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key
from pynput.mouse import Button
from pynput.mouse import Controller as MouseController

from app.core.control_flow import ControlFlowError, find_if_block, validate_control_flow
from app.core.models import (
    Action,
    ActionType,
    ClickPhase,
    KeyPhase,
    MouseButton,
    OnFail,
    Preset,
)
from app.core import mouse_input
from app.core.monitors import to_global
from app.core.settings import get_settings
from app.core.vision import CaptureSpec, find_template, find_text_boxes, is_ocr_enabled

StatusCallback = Callable[[str], None]
StepCallback = Callable[[int | None], None]


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

IF_TYPES = {ActionType.IF_TEXT, ActionType.IF_IMAGE}
VISION_FIND = {ActionType.FIND_TEXT, ActionType.FIND_IMAGE}
VISION_WAIT = {ActionType.WAIT_TEXT, ActionType.WAIT_IMAGE}
OCR_ACTION_TYPES = {ActionType.FIND_TEXT, ActionType.WAIT_TEXT, ActionType.IF_TEXT}


def resolve_key(name: str) -> Any:
    """Convert a stored key string into a pynput key token."""
    if not name:
        raise ValueError("Empty key name")
    lowered = name.lower()
    if lowered in SPECIAL_KEYS:
        return SPECIAL_KEYS[lowered]
    if len(name) == 1:
        return name
    attr = getattr(Key, lowered, None)
    if attr is not None:
        return attr
    return name


class MacroPlayer:
    """Execute preset actions with stop/pause, vision, and if/else support."""

    def __init__(
        self,
        on_status: StatusCallback | None = None,
        on_step: StepCallback | None = None,
    ) -> None:
        self._on_status = on_status or (lambda _msg: None)
        self._on_step = on_step or (lambda _idx: None)
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

    @property
    def is_paused(self) -> bool:
        """True while playback is paused (Event cleared)."""
        return self.is_running and not self._pause.is_set()

    def play(self, preset: Preset) -> None:
        """Start playback of the given preset on a worker thread."""
        if self.is_running:
            self._on_status("Already playing")
            return
        if not preset.actions:
            self._on_status("No actions to play")
            return
        try:
            validate_control_flow(preset.actions)
        except ControlFlowError as exc:
            self._on_status(f"Control flow error: {exc}")
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
        aborted = False
        try:
            while infinite or round_no < loops:
                if self._stop.is_set():
                    break
                round_no += 1
                self._on_status(
                    f"Playing round {round_no}" + (" (∞)" if infinite else f"/{loops}")
                )
                if not self._run_actions(preset.actions, preset.monitor_index, preset.jitter_ms):
                    aborted = True
                    break
        finally:
            self._release_all()
            self._on_step(None)
            if self._stop.is_set() or aborted:
                self._on_status("Stopped")
            else:
                self._on_status("Finished")

    def _run_actions(self, actions: list[Action], monitor_index: int, jitter_ms: int) -> bool:
        """Run actions with index jumps for if/else. Return False if aborted."""
        i = 0
        # When then-branch is taken, map matching else index -> endif index to skip else body.
        skip_else_to_endif: dict[int, int] = {}
        while i < len(actions):
            if self._stop.is_set():
                return False
            self._pause.wait()
            if self._stop.is_set():
                return False

            if i in skip_else_to_endif:
                i = skip_else_to_endif.pop(i) + 1
                continue

            action = actions[i]
            self._on_step(i)

            if action.type == ActionType.ELSE:
                # Executing else-branch body; marker itself is a no-op.
                i += 1
                continue

            if action.type == ActionType.ENDIF:
                i += 1
                continue

            if action.type in IF_TYPES:
                try:
                    block = find_if_block(actions, i)
                except ControlFlowError as exc:
                    self._on_status(f"Control flow error: {exc}")
                    return False
                self._on_status(f"Checking {action.summary()}…")
                ok = self._eval_condition(action, monitor_index)
                if self._stop.is_set():
                    return False
                if ok:
                    if block.else_index is not None:
                        skip_else_to_endif[block.else_index] = block.endif_index
                    i = i + 1
                elif block.else_index is not None:
                    i = block.else_index + 1
                else:
                    i = block.endif_index + 1
                continue

            should_stop = self._execute(action, monitor_index)
            if should_stop:
                return False

            wait_ms = action.after_ms
            if wait_ms <= 0 and action.type not in (
                ActionType.DELAY,
                ActionType.MOUSE_DRAG,
                ActionType.WAIT_TEXT,
                ActionType.WAIT_IMAGE,
            ):
                wait_ms = action.delay_ms
            if jitter_ms > 0 and action.type not in (
                ActionType.DELAY,
                ActionType.MOUSE_DRAG,
                ActionType.WAIT_TEXT,
                ActionType.WAIT_IMAGE,
            ):
                wait_ms += random.randint(0, jitter_ms)
            if not self._wait_interruptible(wait_ms / 1000.0):
                return False
            i += 1
        return True

    def _vision_monitor(self, action: Action, default_monitor: int) -> int:
        """Resolve which monitor a vision action should click on."""
        if action.capture_monitor is not None:
            return int(action.capture_monitor)
        return default_monitor

    def _ocr_disabled_skip(self, action: Action) -> bool:
        """True when a text-OCR action should be skipped (settings)."""
        return action.type in OCR_ACTION_TYPES and not is_ocr_enabled()

    def _eval_condition(self, action: Action, monitor_index: int) -> bool:
        """Evaluate if_text / if_image using a single scan (timeout once)."""
        if action.type == ActionType.IF_TEXT and self._ocr_disabled_skip(action):
            self._on_status("OCR disabled — if_text treated as false")
            return False
        capture = CaptureSpec.from_action(action, monitor_index)
        deadline = time.monotonic() + max(0, action.timeout_ms) / 1000.0
        while True:
            if self._stop.is_set():
                return False
            try:
                if action.type == ActionType.IF_TEXT:
                    if find_text_boxes(capture.monitor_index, action.query, capture=capture):
                        return True
                elif action.type == ActionType.IF_IMAGE:
                    if find_template(
                        capture.monitor_index,
                        action.image_path,
                        action.threshold,
                        capture=capture,
                    ):
                        return True
            except Exception as exc:
                self._on_status(f"Vision error: {exc}")
                return False
            if time.monotonic() >= deadline:
                return False
            if not self._wait_interruptible(0.25):
                return False

    def _execute(self, action: Action, monitor_index: int) -> bool:
        """Execute one action. Return True if playback should abort."""
        if action.type in VISION_FIND:
            return self._exec_find(action, monitor_index)
        if action.type in VISION_WAIT:
            return self._exec_wait(action, monitor_index)

        if action.type == ActionType.DELAY:
            if action.delay_min_ms is not None and action.delay_max_ms is not None:
                low = min(action.delay_min_ms, action.delay_max_ms)
                high = max(action.delay_min_ms, action.delay_max_ms)
                ms = random.randint(low, high)
            else:
                ms = action.delay_ms
            return not self._wait_interruptible(ms / 1000.0)

        if action.type == ActionType.MOUSE_MOVE:
            gx, gy = to_global(monitor_index, int(action.x or 0), int(action.y or 0))
            return not self._move_to_global(gx, gy)

        if action.type == ActionType.MOUSE_DRAG:
            return self._exec_drag(action, monitor_index)

        if action.type == ActionType.MOUSE_CLICK:
            gx, gy = to_global(monitor_index, int(action.x or 0), int(action.y or 0))
            if not self._move_to_global(gx, gy):
                return True
            if action.click_phase != ClickPhase.UP and not self._hover_before_click():
                return True
            btn = MOUSE_BUTTONS[action.button or MouseButton.LEFT]
            if action.click_phase == ClickPhase.DOWN:
                self._mouse.press(btn)
                self._track_button(btn, pressed=True)
            elif action.click_phase == ClickPhase.UP:
                self._mouse.release(btn)
                self._track_button(btn, pressed=False)
            else:
                self._mouse.click(btn, max(1, action.click_count or 1))
            return False

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
            return False

        if action.type == ActionType.HOTKEY:
            tokens = [resolve_key(k) for k in action.keys]
            for t in tokens:
                self._keyboard.press(t)
            for t in reversed(tokens):
                self._keyboard.release(t)
            return False

        if action.type == ActionType.HOLD:
            if action.key:
                token = resolve_key(action.key)
                self._keyboard.press(token)
                self._track_key(token, pressed=True)
                if not self._wait_interruptible(action.hold_ms / 1000.0):
                    return True
                self._keyboard.release(token)
                self._track_key(token, pressed=False)
            else:
                btn = MOUSE_BUTTONS[action.button or MouseButton.LEFT]
                if action.x is not None and action.y is not None:
                    gx, gy = to_global(monitor_index, int(action.x), int(action.y))
                    if not self._move_to_global(gx, gy):
                        return True
                self._mouse.press(btn)
                self._track_button(btn, pressed=True)
                if not self._wait_interruptible(action.hold_ms / 1000.0):
                    return True
                self._mouse.release(btn)
                self._track_button(btn, pressed=False)
            return False

        return False

    def _click_local(self, monitor_index: int, x: int, y: int, button: MouseButton | None) -> None:
        """Click at monitor-local coordinates (humanized SendInput move when enabled)."""
        gx, gy = to_global(monitor_index, x, y)
        if not self._move_to_global(gx, gy):
            return
        if not self._hover_before_click():
            return
        self._mouse.click(MOUSE_BUTTONS[button or MouseButton.LEFT], 1)

    def _set_cursor(self, gx: int, gy: int) -> None:
        """Place cursor using SendInput on Windows; fall back to pynput elsewhere."""
        if mouse_input.uses_sendinput():
            mouse_input.move_absolute(int(gx), int(gy))
        else:
            self._mouse.position = (int(gx), int(gy))

    def _cursor_xy(self) -> tuple[int, int]:
        """Read cursor position (prefer Win32 when available)."""
        if mouse_input.uses_sendinput():
            try:
                return mouse_input.cursor_pos()
            except OSError:
                pass
        try:
            x0, y0 = self._mouse.position
            return int(x0), int(y0)
        except Exception:
            return 0, 0

    def _hover_before_click(self) -> bool:
        """Brief dwell after arriving at target (hover / enter gates)."""
        ms = max(0, int(get_settings().mouse_hover_ms))
        if ms <= 0:
            return not self._stop.is_set()
        # Small random dwell so timing is not identical every click.
        wait = (ms / 1000.0) * random.uniform(0.85, 1.25)
        return self._wait_interruptible(wait)

    def _move_to_global(self, gx: int, gy: int) -> bool:
        """Move cursor to global (gx, gy) via SendInput path. False if stopped."""
        settings = get_settings()
        x0, y0 = self._cursor_xy()
        dx = gx - x0
        dy = gy - y0
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 1.5 or not settings.humanize_mouse:
            self._set_cursor(gx, gy)
            return not self._stop.is_set()

        # If already near the target, back out first so the cursor *enters* the hit box.
        if dist < 28:
            back = random.randint(48, 110)
            angle = random.uniform(0, 6.28318)
            ax = int(round(gx + math.cos(angle) * back))
            ay = int(round(gy + math.sin(angle) * back))
            self._set_cursor(ax, ay)
            if not self._wait_interruptible(random.uniform(0.02, 0.05)):
                return False
            x0, y0 = self._cursor_xy()
            dx = gx - x0
            dy = gy - y0
            dist = max(1.0, (dx * dx + dy * dy) ** 0.5)

        # Duration scales with distance; slight random variation.
        base_ms = max(40, int(settings.mouse_move_ms))
        duration = (base_ms / 1000.0) * (0.55 + min(dist, 900.0) / 600.0)
        duration *= random.uniform(0.85, 1.2)
        duration = max(0.05, min(3.0, duration))

        curve = max(0.0, min(1.0, float(settings.mouse_curve)))
        # Quadratic Bezier control point: offset perpendicular to the path.
        mx = (x0 + gx) / 2.0
        my = (y0 + gy) / 2.0
        if dist > 1:
            nx, ny = -dy / dist, dx / dist
        else:
            nx, ny = 0.0, 1.0
        offset = dist * curve * random.uniform(0.25, 0.85) * random.choice((-1.0, 1.0))
        cx = mx + nx * offset + random.uniform(-4, 4)
        cy = my + ny * offset + random.uniform(-4, 4)

        step_s = 1.0 / 120.0
        steps = max(8, int(duration / step_s))
        for i in range(1, steps + 1):
            if self._stop.is_set():
                return False
            # Ease-in-out + tiny speed wobble so motion is not perfectly uniform.
            u = i / steps
            t = u * u * (3.0 - 2.0 * u)
            t = max(0.0, min(1.0, t + random.uniform(-0.012, 0.012)))
            omt = 1.0 - t
            x = omt * omt * x0 + 2 * omt * t * cx + t * t * gx
            y = omt * omt * y0 + 2 * omt * t * cy + t * t * gy
            if i < steps:
                x += random.uniform(-0.6, 0.6) * curve
                y += random.uniform(-0.6, 0.6) * curve
            self._set_cursor(int(round(x)), int(round(y)))
            if not self._wait_interruptible(duration / steps):
                return False

        self._set_cursor(gx, gy)
        return not self._stop.is_set()

    def _exec_drag(self, action: Action, monitor_index: int) -> bool:
        """Press, move start→end at constant speed over hold_ms, then release."""
        x0 = int(action.x or 0)
        y0 = int(action.y or 0)
        x1 = int(action.end_x if action.end_x is not None else x0)
        y1 = int(action.end_y if action.end_y is not None else y0)
        duration = max(1, int(action.hold_ms or 1)) / 1000.0
        btn = MOUSE_BUTTONS[action.button or MouseButton.LEFT]
        gx0, gy0 = to_global(monitor_index, x0, y0)
        gx1, gy1 = to_global(monitor_index, x1, y1)
        if not self._move_to_global(gx0, gy0):
            return True
        self._mouse.press(btn)
        self._track_button(btn, pressed=True)

        # ~120 Hz constant-speed interpolation (not replaying recorded jitter).
        step_s = 1.0 / 120.0
        steps = max(1, int(duration / step_s))
        for i in range(1, steps + 1):
            if self._stop.is_set():
                self._mouse.release(btn)
                self._track_button(btn, pressed=False)
                return True
            t = i / steps
            self._set_cursor(
                int(gx0 + (gx1 - gx0) * t),
                int(gy0 + (gy1 - gy0) * t),
            )
            if not self._wait_interruptible(duration / steps):
                self._mouse.release(btn)
                self._track_button(btn, pressed=False)
                return True

        self._set_cursor(gx1, gy1)
        self._mouse.release(btn)
        self._track_button(btn, pressed=False)
        return False

    def _exec_find(self, action: Action, monitor_index: int) -> bool:
        """Find text/image within timeout and click; honor on_fail."""
        if action.type == ActionType.FIND_TEXT and self._ocr_disabled_skip(action):
            self._on_status("OCR disabled — skipped find_text")
            return False
        capture = CaptureSpec.from_action(action, monitor_index)
        click_mon = self._vision_monitor(action, monitor_index)
        self._on_status(f"Looking for {action.summary()}…")
        deadline = time.monotonic() + max(0, action.timeout_ms) / 1000.0
        while True:
            if self._stop.is_set():
                return True
            try:
                if action.type == ActionType.FIND_TEXT:
                    hits = find_text_boxes(
                        capture.monitor_index, action.query, capture=capture
                    )
                    if hits:
                        self._click_local(click_mon, hits[0].x, hits[0].y, action.button)
                        self._on_status(f'Clicked text "{hits[0].text}"')
                        return False
                else:
                    hit = find_template(
                        capture.monitor_index,
                        action.image_path,
                        action.threshold,
                        capture=capture,
                    )
                    if hit is not None:
                        self._click_local(click_mon, hit.x, hit.y, action.button)
                        self._on_status(f"Clicked image (score {hit.score:.2f})")
                        return False
            except Exception as exc:
                self._on_status(f"Vision error: {exc}")
                return action.on_fail == OnFail.STOP
            if time.monotonic() >= deadline:
                self._on_status("Not found")
                return action.on_fail == OnFail.STOP
            if not self._wait_interruptible(0.25):
                return True

    def _exec_wait(self, action: Action, monitor_index: int) -> bool:
        """Wait until text/image appears or timeout."""
        if action.type == ActionType.WAIT_TEXT and self._ocr_disabled_skip(action):
            self._on_status("OCR disabled — skipped wait_text")
            return False
        capture = CaptureSpec.from_action(action, monitor_index)
        self._on_status(f"Waiting {action.summary()}…")
        deadline = time.monotonic() + max(0, action.timeout_ms) / 1000.0
        while True:
            if self._stop.is_set():
                return True
            try:
                if action.type == ActionType.WAIT_TEXT:
                    if find_text_boxes(
                        capture.monitor_index, action.query, capture=capture
                    ):
                        self._on_status("Text found")
                        return False
                else:
                    if find_template(
                        capture.monitor_index,
                        action.image_path,
                        action.threshold,
                        capture=capture,
                    ):
                        self._on_status("Image found")
                        return False
            except Exception as exc:
                self._on_status(f"Vision error: {exc}")
                return action.on_fail == OnFail.STOP
            if time.monotonic() >= deadline:
                self._on_status("Wait timed out")
                return action.on_fail == OnFail.STOP
            if not self._wait_interruptible(0.25):
                return True

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
