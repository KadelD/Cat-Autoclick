"""Floating recording HUD with hotkey tips."""

from __future__ import annotations

import tkinter as tk

from app.core.monitors import get_monitor
from app.core.settings import AppSettings, get_settings
from app.ui_ctk import theme as T


class RecordHud:
    """Small topmost tip panel shown while recording."""

    def __init__(
        self,
        master: tk.Misc,
        monitor_index: int = 0,
        settings: AppSettings | None = None,
    ) -> None:
        self._win = tk.Toplevel(master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        try:
            self._win.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        self._win.configure(bg=T.PANEL)

        mon = get_monitor(monitor_index)
        width, height = 250, 168
        x = mon.x + mon.width - width - 16
        y = mon.y + 48
        self._win.geometry(f"{width}x{height}+{x}+{y}")

        frame = tk.Frame(self._win, bg=T.PANEL, padx=12, pady=10)
        frame.pack(fill="both", expand=True)

        self._title = tk.Label(
            frame,
            text="Recording…",
            bg=T.PANEL,
            fg=T.RECORD,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self._title.pack(fill="x")

        tips = _tips_text(settings or get_settings())
        self._body = tk.Label(
            frame,
            text=tips,
            bg=T.PANEL,
            fg=T.WHITE,
            font=("Segoe UI", 9),
            justify="left",
            anchor="nw",
        )
        self._body.pack(fill="both", expand=True, pady=(8, 0))

    def set_status(self, message: str) -> None:
        """Update the HUD title line (e.g. OCR setup)."""
        try:
            self._title.configure(text=message)
        except tk.TclError:
            pass

    def destroy(self) -> None:
        """Close the HUD window."""
        try:
            self._win.destroy()
        except tk.TclError:
            pass


def _tips_text(settings: AppSettings) -> str:
    """Build HUD tip lines from current hotkey settings."""
    lines = [
        f"{settings.display_hotkey('record')}  stop record",
        f"{settings.display_hotkey('stop')} stop all",
    ]
    if settings.ocr_enabled:
        lines.append(f"{settings.display_hotkey('ocr_full')}  OCR full")
        lines.append(f"{settings.display_hotkey('ocr_area')}  OCR area")
    lines.append("Plain keys still record")
    return "\n".join(lines)
