"""Compact OCR action settings dialog used during recording."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from app.core.models import Action, ActionType, MouseButton, OnFail
from app.ui_ctk import theme as T

OcrCallback = Callable[[Action], None]

_TYPE_CHOICES = (
    ("Find text", ActionType.FIND_TEXT),
    ("Wait text", ActionType.WAIT_TEXT),
    ("If text", ActionType.IF_TEXT),
)


class OcrCaptureDialog(ctk.CTkToplevel):
    """Small topmost form to finish an OCR step after F6/F7 capture."""

    def __init__(
        self,
        master: ctk.CTk | ctk.CTkToplevel,
        *,
        monitor_index: int,
        region_x: int = 0,
        region_y: int = 0,
        region_w: int = 0,
        region_h: int = 0,
        on_ok: OcrCallback | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("OCR step")
        self.geometry("400x460")
        self.minsize(360, 420)
        self.resizable(False, False)
        self.configure(fg_color=T.PANEL)
        self._on_ok = on_ok or (lambda _a: None)
        self._on_cancel = on_cancel or (lambda: None)
        self._monitor_index = monitor_index
        self._region = (region_x, region_y, region_w, region_h)
        self._closed = False

        self.protocol("WM_DELETE_WINDOW", self._cancel)

        # Parent may be a withdrawn overlay host while the main window is hidden —
        # force this dialog visible and on top.
        self.after(0, self._force_show)

        ctk.CTkLabel(
            self,
            text="OCR capture",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=T.WHITE,
        ).pack(anchor="w", padx=16, pady=(14, 4))

        scope = (
            f"Full monitor {monitor_index}"
            if region_w <= 0 or region_h <= 0
            else f"Region {region_x},{region_y} {region_w}x{region_h} (mon {monitor_index})"
        )
        ctk.CTkLabel(self, text=scope, text_color=T.MUTED).pack(anchor="w", padx=16)

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=16, pady=10)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Type", text_color=T.MUTED).grid(row=0, column=0, sticky="w", pady=4)
        self._type = ctk.CTkOptionMenu(
            form,
            values=[label for label, _ in _TYPE_CHOICES],
            command=self._on_type_change,
            fg_color=T.NAVY,
            button_color=T.PURPLE_DIM,
            button_hover_color=T.PURPLE,
            dropdown_fg_color=T.PANEL,
            text_color=T.WHITE,
        )
        self._type.set("Find text")
        self._type.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)

        ctk.CTkLabel(form, text="Text", text_color=T.MUTED).grid(row=1, column=0, sticky="w", pady=4)
        self._query = ctk.CTkEntry(
            form, fg_color=T.INPUT, border_color=T.BORDER, text_color=T.WHITE
        )
        self._query.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)
        self._query.bind("<Return>", lambda _e: self._ok())

        ctk.CTkLabel(form, text="Timeout ms", text_color=T.MUTED).grid(
            row=2, column=0, sticky="w", pady=4
        )
        self._timeout = ctk.CTkEntry(
            form, width=100, fg_color=T.INPUT, border_color=T.BORDER, text_color=T.WHITE
        )
        self._timeout.insert(0, "5000")
        self._timeout.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)
        self._timeout.bind("<Return>", lambda _e: self._ok())

        self._fail_label = ctk.CTkLabel(form, text="On fail", text_color=T.MUTED)
        self._fail_label.grid(row=3, column=0, sticky="w", pady=4)
        self._on_fail = ctk.CTkOptionMenu(
            form,
            values=["stop", "continue"],
            fg_color=T.NAVY,
            button_color=T.PURPLE_DIM,
            button_hover_color=T.PURPLE,
            dropdown_fg_color=T.PANEL,
            text_color=T.WHITE,
        )
        self._on_fail.set("stop")
        self._on_fail.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=4)

        self._btn_label = ctk.CTkLabel(form, text="Click", text_color=T.MUTED)
        self._btn_label.grid(row=4, column=0, sticky="w", pady=4)
        self._button = ctk.CTkOptionMenu(
            form,
            values=["left", "right", "middle"],
            fg_color=T.NAVY,
            button_color=T.PURPLE_DIM,
            button_hover_color=T.PURPLE,
            dropdown_fg_color=T.PANEL,
            text_color=T.WHITE,
        )
        self._button.set("left")
        self._button.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=4)

        self._error = ctk.CTkLabel(self, text="", text_color=T.RECORD)
        self._error.pack(anchor="w", padx=16)

        # Keep confirm buttons pinned at the bottom so they are never clipped.
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(side="bottom", fill="x", padx=16, pady=(8, 16))
        ctk.CTkButton(
            actions,
            text="Cancel",
            width=100,
            height=36,
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            command=self._cancel,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            actions,
            text="Add step",
            width=120,
            height=36,
            fg_color=T.CYAN_DIM,
            hover_color=T.CYAN,
            text_color=T.BG,
            command=self._ok,
        ).pack(side="right")

        self._on_type_change(self._type.get())

    def _force_show(self) -> None:
        """Ensure the dialog is visible even when the parent host is withdrawn."""
        try:
            self.deiconify()
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self._query.focus_set()
        except Exception:
            pass

    def _selected_type(self) -> ActionType:
        label = self._type.get()
        for name, atype in _TYPE_CHOICES:
            if name == label:
                return atype
        return ActionType.FIND_TEXT

    def _on_type_change(self, _value: str) -> None:
        """Show/hide on_fail and click button based on action kind."""
        atype = self._selected_type()
        show_fail = atype in (ActionType.FIND_TEXT, ActionType.WAIT_TEXT)
        show_btn = atype == ActionType.FIND_TEXT
        for widget, visible in (
            (self._fail_label, show_fail),
            (self._on_fail, show_fail),
            (self._btn_label, show_btn),
            (self._button, show_btn),
        ):
            if visible:
                widget.grid()
            else:
                widget.grid_remove()

    def _ok(self) -> None:
        query = self._query.get().strip()
        if not query:
            self._error.configure(text="Text is required")
            return
        try:
            timeout = max(0, int(self._timeout.get().strip()))
        except ValueError:
            self._error.configure(text="Timeout must be a number")
            return
        atype = self._selected_type()
        rx, ry, rw, rh = self._region
        action = Action(
            type=atype,
            query=query,
            timeout_ms=timeout,
            on_fail=OnFail(self._on_fail.get()),
            button=MouseButton(self._button.get()) if atype == ActionType.FIND_TEXT else None,
            capture_monitor=self._monitor_index,
            region_x=rx,
            region_y=ry,
            region_w=rw,
            region_h=rh,
        )
        self._closed = True
        self._on_ok(action)
        self.destroy()

    def _cancel(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._on_cancel()
        self.destroy()
