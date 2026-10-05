"""Application settings dialog (hotkeys, window, startup, OCR)."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk
from pynput import keyboard

from app.core.settings import (
    AppSettings,
    apply_auto_start,
    format_hotkey_display,
    normalize_hotkey,
    read_auto_start_enabled,
    save_settings,
)
from app.ui import theme as T

ApplyCallback = Callable[[AppSettings], None]

_HOTKEY_FIELDS = (
    ("hotkey_play", "Play"),
    ("hotkey_record", "Record"),
    ("hotkey_stop", "Stop"),
    ("hotkey_ocr_full", "OCR full"),
    ("hotkey_ocr_area", "OCR area"),
)


class SettingsDialog(ctk.CTkToplevel):
    """Modal-ish settings editor; Save applies and persists."""

    def __init__(
        self,
        master: ctk.CTk,
        settings: AppSettings,
        on_apply: ApplyCallback | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Settings")
        self.geometry("460x560")
        self.minsize(420, 520)
        self.configure(fg_color=T.PANEL)
        self.attributes("-topmost", True)
        self._on_apply = on_apply or (lambda _s: None)
        self._settings = AppSettings.from_dict(settings.to_dict())
        self._capture_field: str | None = None
        self._key_listener: keyboard.Listener | None = None
        self._hotkey_labels: dict[str, ctk.CTkLabel] = {}
        self._closed = False

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        ctk.CTkLabel(
            self,
            text="Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=T.WHITE,
        ).pack(anchor="w", padx=16, pady=(14, 4))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        self._section(body, "Hotkeys")
        tip = ctk.CTkLabel(
            body,
            text="Click Set, then press a shortcut (modifiers + key).",
            text_color=T.MUTED,
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        tip.pack(fill="x", padx=8, pady=(0, 6))
        for field, title in _HOTKEY_FIELDS:
            self._hotkey_row(body, field, title)

        self._section(body, "Window")
        self._start_min = self._check(
            body, "Start minimized", self._settings.start_minimized
        )
        self._hide_rec = self._check(
            body,
            "Hide window while recording (HUD stays visible)",
            self._settings.hide_on_record,
        )

        self._section(body, "Startup")
        # Reflect OS state if it drifted from the file.
        auto = self._settings.auto_start or read_auto_start_enabled()
        self._auto_start = self._check(body, "Launch with Windows", auto)

        self._section(body, "Vision / OCR")
        self._ocr = self._check(
            body,
            "Enable OCR (EasyOCR Thai + English)",
            self._settings.ocr_enabled,
        )
        ctk.CTkLabel(
            body,
            text="Turn off to keep the app light. Image find still works.",
            text_color=T.MUTED,
            font=ctk.CTkFont(size=11),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=8, pady=(0, 8))

        self._error = ctk.CTkLabel(self, text="", text_color=T.RECORD)
        self._error.pack(anchor="w", padx=16)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(4, 14))
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
            text="Save",
            width=110,
            height=36,
            fg_color=T.CYAN_DIM,
            hover_color=T.CYAN,
            text_color=T.BG,
            command=self._save,
        ).pack(side="right")

        self.after(40, self._force_show)

    def _force_show(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _section(self, master: ctk.CTkBaseClass, title: str) -> None:
        ctk.CTkLabel(
            master,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=T.CYAN,
            anchor="w",
        ).pack(fill="x", padx=8, pady=(12, 4))

    def _check(self, master: ctk.CTkBaseClass, text: str, value: bool) -> ctk.CTkCheckBox:
        box = ctk.CTkCheckBox(
            master,
            text=text,
            text_color=T.WHITE,
            fg_color=T.PURPLE,
            hover_color=T.PURPLE_DIM,
            border_color=T.BORDER,
        )
        if value:
            box.select()
        else:
            box.deselect()
        box.pack(anchor="w", padx=8, pady=4)
        return box

    def _checked(self, box: ctk.CTkCheckBox) -> bool:
        return bool(box.get())

    def _hotkey_row(self, master: ctk.CTkBaseClass, field: str, title: str) -> None:
        row = ctk.CTkFrame(master, fg_color=T.BG, corner_radius=8)
        row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(row, text=title, width=90, anchor="w", text_color=T.MUTED).pack(
            side="left", padx=(10, 6), pady=8
        )
        value = format_hotkey_display(getattr(self._settings, field))
        label = ctk.CTkLabel(row, text=value, anchor="w", text_color=T.WHITE)
        label.pack(side="left", fill="x", expand=True, padx=4)
        self._hotkey_labels[field] = label
        ctk.CTkButton(
            row,
            text="Set",
            width=56,
            height=28,
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            command=lambda f=field: self._begin_capture(f),
        ).pack(side="right", padx=8, pady=6)

    def _begin_capture(self, field: str) -> None:
        """Listen for the next keyboard chord and assign it to field."""
        self._stop_capture()
        self._capture_field = field
        self._hotkey_labels[field].configure(text="Press keys…", text_color=T.CYAN)
        self._error.configure(text="")
        held: set[str] = set()

        def on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
            name = _key_name(key)
            if not name:
                return
            held.add(name)
            # Commit when a non-modifier is pressed with optional modifiers.
            if name not in ("ctrl", "alt", "shift", "win"):
                mods = [m for m in ("ctrl", "alt", "shift", "win") if m in held]
                chord = normalize_hotkey("+".join(mods + [name]))
                self.after(0, lambda: self._finish_capture(field, chord))

        self._key_listener = keyboard.Listener(on_press=on_press)
        self._key_listener.start()

    def _finish_capture(self, field: str, chord: str) -> None:
        self._stop_capture()
        if not chord:
            self._hotkey_labels[field].configure(
                text=format_hotkey_display(getattr(self._settings, field)),
                text_color=T.WHITE,
            )
            return
        setattr(self._settings, field, chord)
        self._hotkey_labels[field].configure(
            text=format_hotkey_display(chord), text_color=T.WHITE
        )

    def _stop_capture(self) -> None:
        self._capture_field = None
        if self._key_listener is not None:
            try:
                self._key_listener.stop()
            except Exception:
                pass
            self._key_listener = None

    def _collect(self) -> AppSettings | None:
        s = AppSettings(
            hotkey_play=self._settings.hotkey_play,
            hotkey_record=self._settings.hotkey_record,
            hotkey_stop=self._settings.hotkey_stop,
            hotkey_ocr_full=self._settings.hotkey_ocr_full,
            hotkey_ocr_area=self._settings.hotkey_ocr_area,
            start_minimized=self._checked(self._start_min),
            hide_on_record=self._checked(self._hide_rec),
            auto_start=self._checked(self._auto_start),
            ocr_enabled=self._checked(self._ocr),
        )
        err = s.validate_hotkeys()
        if err:
            self._error.configure(text=err)
            return None
        return s

    def _save(self) -> None:
        settings = self._collect()
        if settings is None:
            return
        try:
            apply_auto_start(settings.auto_start)
        except Exception as exc:
            self._error.configure(text=f"Auto-start failed: {exc}")
            return
        save_settings(settings)
        self._closed = True
        self._stop_capture()
        self._on_apply(settings)
        self.destroy()

    def _cancel(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop_capture()
        self.destroy()


def _key_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    """Normalize pynput key to settings token."""
    if isinstance(key, keyboard.KeyCode):
        if key.char and key.char.isprintable():
            return key.char.lower()
        # Function keys often arrive as Key.fN, not KeyCode.
        return None
    name = str(key).replace("Key.", "")
    aliases = {
        "ctrl_l": "ctrl",
        "ctrl_r": "ctrl",
        "alt_l": "alt",
        "alt_r": "alt",
        "shift_l": "shift",
        "shift_r": "shift",
        "cmd": "win",
        "cmd_l": "win",
        "cmd_r": "win",
    }
    return aliases.get(name, name)
