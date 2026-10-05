"""Fullscreen drag picker to choose a capture rectangle on one monitor."""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk

from app.core.monitors import get_monitor

RegionCallback = Callable[[int, int, int, int], None]


def pick_region(
    master: tk.Misc,
    monitor_index: int,
    on_done: RegionCallback,
    on_cancel: Callable[[], None] | None = None,
) -> None:
    """
    Open a dim overlay on the monitor; user drags a rectangle.

    Calls on_done(x, y, w, h) in monitor-local coordinates, or on_cancel().
    """
    mon = get_monitor(monitor_index)
    win = tk.Toplevel(master)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    try:
        win.attributes("-alpha", 0.35)
    except tk.TclError:
        pass
    win.geometry(f"{mon.width}x{mon.height}+{mon.x}+{mon.y}")
    win.configure(bg="#000000")

    canvas = tk.Canvas(win, bg="#0a0a12", highlightthickness=0, cursor="crosshair")
    canvas.pack(fill="both", expand=True)
    canvas.create_text(
        mon.width // 2,
        40,
        text="Drag to select capture region · Esc to cancel",
        fill="#4FC3F7",
        font=("Segoe UI", 16, "bold"),
    )

    state: dict[str, int | None] = {"x0": None, "y0": None, "rect": None}

    def _clear() -> None:
        if state["rect"] is not None:
            canvas.delete(state["rect"])
            state["rect"] = None

    def on_press(event: tk.Event) -> None:
        state["x0"] = int(event.x)
        state["y0"] = int(event.y)
        _clear()
        state["rect"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#8B5CF6", width=2
        )

    def on_drag(event: tk.Event) -> None:
        if state["x0"] is None or state["y0"] is None or state["rect"] is None:
            return
        canvas.coords(state["rect"], state["x0"], state["y0"], event.x, event.y)

    def finish(x0: int, y0: int, x1: int, y1: int) -> None:
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        w = max(1, right - left)
        h = max(1, bottom - top)
        win.destroy()
        on_done(left, top, w, h)

    def on_release(event: tk.Event) -> None:
        if state["x0"] is None or state["y0"] is None:
            return
        finish(int(state["x0"]), int(state["y0"]), int(event.x), int(event.y))

    def cancel(_event: tk.Event | None = None) -> None:
        win.destroy()
        if on_cancel:
            on_cancel()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    win.bind("<Escape>", cancel)
    win.focus_force()
