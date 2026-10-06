"""Simple hover tooltip for CustomTkinter / tk widgets."""

from __future__ import annotations

import tkinter as tk


class HoverTip:
    """Show a small floating tip while the pointer is over a widget."""

    def __init__(self, widget: tk.Misc, text: str) -> None:
        self._widget = widget
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        """Update tooltip text."""
        self._text = text

    def _show(self, _event=None) -> None:
        if self._tip is not None or not self._text:
            return
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.attributes("-topmost", True)
        label = tk.Label(
            self._tip,
            text=self._text,
            background="#121C33",
            foreground="#F4F7FF",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
            padx=8,
            pady=4,
        )
        label.pack()
        x = self._widget.winfo_rootx() + 18
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
