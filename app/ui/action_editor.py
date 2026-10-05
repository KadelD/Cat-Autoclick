"""Action list and type-aware add-step form in a side-by-side layout."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from app.core.models import (
    Action,
    ActionType,
    ClickPhase,
    KeyPhase,
    MouseButton,
    Preset,
)
from app.ui import theme as T

ChangedCallback = Callable[[], None]
StatusCallback = Callable[[str], None]

TYPE_HINTS = {
    ActionType.MOUSE_CLICK.value: "Set X/Y, mouse button, and click phase.",
    ActionType.MOUSE_MOVE.value: "Move the cursor to X/Y on the selected monitor.",
    ActionType.KEY.value: "Single key — tap, press, or release.",
    ActionType.HOTKEY.value: "Chord like ctrl+c or ctrl+shift+s.",
    ActionType.HOLD.value: "Fill Key OR mouse Button + X/Y (not both).",
    ActionType.DELAY.value: "Wait a fixed number of milliseconds.",
}


class ActionEditor(ctk.CTkFrame):
    """Actions stay visible on the left; Add step scrolls on the right."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_changed: ChangedCallback,
        on_status: StatusCallback | None = None,
        **kwargs,
    ) -> None:
        kwargs.setdefault("fg_color", T.PANEL)
        kwargs.setdefault("corner_radius", 14)
        super().__init__(master, **kwargs)
        self._on_changed = on_changed
        self._on_status = on_status or (lambda _m: None)
        self._preset: Preset | None = None
        self._selected_index: int | None = None
        self._field_rows: dict[str, list[ctk.CTkBaseClass]] = {}

        self.grid_columnconfigure(0, weight=3, minsize=280)
        self.grid_columnconfigure(1, weight=2, minsize=260)
        self.grid_rowconfigure(0, weight=1)

        # --- Left: action list (always keeps vertical space) ---
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1, minsize=180)

        ctk.CTkLabel(
            left,
            text="Actions",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=T.WHITE,
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 6))

        self._list = ctk.CTkScrollableFrame(
            left,
            fg_color=T.PANEL_ALT,
            corner_radius=10,
            scrollbar_button_color=T.NAVY,
            scrollbar_button_hover_color=T.PURPLE_DIM,
        )
        self._list.grid(row=1, column=0, sticky="nsew")

        tools = ctk.CTkFrame(left, fg_color="transparent")
        tools.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        for text, cmd in (
            ("Up", self._move_up),
            ("Down", self._move_down),
            ("Remove", self._remove),
            ("Clear", self._clear),
        ):
            ctk.CTkButton(
                tools,
                text=text,
                width=70,
                height=30,
                fg_color=T.NAVY,
                hover_color=T.PURPLE_DIM,
                text_color=T.WHITE,
                command=cmd,
            ).pack(side="left", padx=3)

        # --- Right: add-step form (independent scroll, never steals list height) ---
        form_wrap = ctk.CTkFrame(self, fg_color=T.PANEL_ALT, corner_radius=12)
        form_wrap.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        form_wrap.grid_columnconfigure(0, weight=1)
        form_wrap.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            form_wrap,
            text="Add step",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=T.CYAN,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self._form = ctk.CTkScrollableFrame(
            form_wrap,
            fg_color="transparent",
            scrollbar_button_color=T.NAVY,
            scrollbar_button_hover_color=T.CYAN_DIM,
        )
        self._form.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self._form.grid_columnconfigure(1, weight=1)

        self._hint = ctk.CTkLabel(
            self._form,
            text=TYPE_HINTS[ActionType.MOUSE_CLICK.value],
            text_color=T.MUTED,
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left",
            wraplength=240,
        )
        self._hint.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 8))

        ctk.CTkLabel(self._form, text="Type", text_color=T.MUTED).grid(
            row=1, column=0, sticky="w", padx=8, pady=4
        )
        self._type = ctk.CTkOptionMenu(
            self._form,
            values=[t.value for t in ActionType],
            command=lambda _v: self._sync_form_visibility(),
            fg_color=T.NAVY,
            button_color=T.PURPLE_DIM,
            button_hover_color=T.PURPLE,
            dropdown_fg_color=T.PANEL,
            dropdown_hover_color=T.NAVY,
            text_color=T.WHITE,
        )
        self._type.set(ActionType.MOUSE_CLICK.value)
        self._type.grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        self._x = self._labeled_entry(2, "X", "100", key="xy")
        self._y = self._labeled_entry(3, "Y", "100", key="xy")
        self._button = self._labeled_option(
            4, "Button", [b.value for b in MouseButton], MouseButton.LEFT.value, key="button"
        )
        self._key = self._labeled_entry(5, "Key", "", placeholder="a / ctrl / f5", key="key")
        self._key.bind("<KeyRelease>", lambda _e: self._sync_hold_mode())
        self._keys = self._labeled_entry(6, "Hotkeys", "", placeholder="ctrl+c", key="hotkeys")
        self._hold = self._labeled_entry(7, "Hold ms", "500", key="hold")
        self._delay = self._labeled_entry(8, "Delay ms", "100", key="delay")
        self._phase = self._labeled_option(
            9, "Phase", ["click", "tap", "down", "up"], "click", key="phase"
        )

        ctk.CTkButton(
            form_wrap,
            text="Add action",
            height=36,
            fg_color=T.PURPLE,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self._add,
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))

        self._sync_form_visibility()

    def _labeled_entry(
        self,
        row: int,
        label: str,
        value: str,
        *,
        placeholder: str = "",
        key: str,
    ) -> ctk.CTkEntry:
        lbl = ctk.CTkLabel(self._form, text=label, text_color=T.MUTED)
        lbl.grid(row=row, column=0, sticky="w", padx=8, pady=4)
        entry = ctk.CTkEntry(
            self._form,
            placeholder_text=placeholder or None,
            fg_color=T.INPUT,
            border_color=T.BORDER,
            text_color=T.WHITE,
        )
        if value:
            entry.insert(0, value)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        self._field_rows.setdefault(key, []).extend([lbl, entry])
        return entry

    def _labeled_option(
        self,
        row: int,
        label: str,
        values: list[str],
        default: str,
        *,
        key: str,
    ) -> ctk.CTkOptionMenu:
        lbl = ctk.CTkLabel(self._form, text=label, text_color=T.MUTED)
        lbl.grid(row=row, column=0, sticky="w", padx=8, pady=4)
        menu = ctk.CTkOptionMenu(
            self._form,
            values=values,
            fg_color=T.NAVY,
            button_color=T.PURPLE_DIM,
            button_hover_color=T.PURPLE,
            dropdown_fg_color=T.PANEL,
            dropdown_hover_color=T.NAVY,
            text_color=T.WHITE,
        )
        menu.set(default)
        menu.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        self._field_rows.setdefault(key, []).extend([lbl, menu])
        return menu

    def set_preset(self, preset: Preset | None) -> None:
        self._preset = preset
        self._selected_index = None
        self._render()

    def append_action(self, action: Action) -> None:
        if self._preset is None:
            return
        self._preset.actions.append(action)
        self._render()
        self._on_changed()

    def _render(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()
        if self._preset is None:
            ctk.CTkLabel(self._list, text="Select or create a preset", text_color=T.MUTED).pack(
                anchor="w", padx=8, pady=8
            )
            return
        if not self._preset.actions:
            ctk.CTkLabel(
                self._list,
                text="No actions yet — record or add a step on the right",
                text_color=T.MUTED,
            ).pack(anchor="w", padx=8, pady=8)
            return
        for i, action in enumerate(self._preset.actions):
            selected = i == self._selected_index
            row = ctk.CTkFrame(
                self._list,
                fg_color=T.PURPLE_DIM if selected else T.BG,
                corner_radius=8,
                border_width=1,
                border_color=T.CYAN if selected else T.BORDER,
            )
            row.pack(fill="x", pady=3, padx=2)
            label = ctk.CTkLabel(
                row,
                text=f"{i + 1}. {action.summary()}",
                anchor="w",
                text_color=T.WHITE,
            )
            label.pack(side="left", fill="x", expand=True, padx=10, pady=8)
            row.bind("<Button-1>", lambda _e, idx=i: self._select(idx))
            label.bind("<Button-1>", lambda _e, idx=i: self._select(idx))

    def _select(self, index: int) -> None:
        self._selected_index = index
        self._render()

    def _move_up(self) -> None:
        if self._preset is None or self._selected_index is None or self._selected_index <= 0:
            return
        i = self._selected_index
        acts = self._preset.actions
        acts[i - 1], acts[i] = acts[i], acts[i - 1]
        self._selected_index = i - 1
        self._render()
        self._on_changed()

    def _move_down(self) -> None:
        if self._preset is None or self._selected_index is None:
            return
        i = self._selected_index
        if i >= len(self._preset.actions) - 1:
            return
        acts = self._preset.actions
        acts[i + 1], acts[i] = acts[i], acts[i + 1]
        self._selected_index = i + 1
        self._render()
        self._on_changed()

    def _remove(self) -> None:
        if self._preset is None or self._selected_index is None:
            return
        del self._preset.actions[self._selected_index]
        self._selected_index = None
        self._render()
        self._on_changed()

    def _clear(self) -> None:
        if self._preset is None:
            return
        self._preset.actions.clear()
        self._selected_index = None
        self._render()
        self._on_changed()

    def _int(self, entry: ctk.CTkEntry, default: int = 0) -> int:
        try:
            return int(entry.get().strip())
        except ValueError:
            return default

    def _add(self) -> None:
        if self._preset is None:
            return
        kind = ActionType(self._type.get())
        if kind == ActionType.MOUSE_CLICK:
            phase_raw = self._phase.get()
            click_phase = ClickPhase.CLICK
            if phase_raw == "down":
                click_phase = ClickPhase.DOWN
            elif phase_raw == "up":
                click_phase = ClickPhase.UP
            action = Action(
                type=kind,
                x=self._int(self._x),
                y=self._int(self._y),
                button=MouseButton(self._button.get()),
                click_phase=click_phase,
            )
        elif kind == ActionType.MOUSE_MOVE:
            action = Action(type=kind, x=self._int(self._x), y=self._int(self._y))
        elif kind == ActionType.KEY:
            key = self._key.get().strip()
            if not key:
                self._on_status("Enter a key name first")
                return
            phase_raw = self._phase.get()
            key_phase = KeyPhase.TAP
            if phase_raw == "down":
                key_phase = KeyPhase.DOWN
            elif phase_raw == "up":
                key_phase = KeyPhase.UP
            action = Action(type=kind, key=key, key_phase=key_phase)
        elif kind == ActionType.HOTKEY:
            parts = [p.strip() for p in self._keys.get().replace("+", " ").split() if p.strip()]
            if not parts:
                self._on_status("Enter a hotkey like ctrl+c")
                return
            action = Action(type=kind, keys=parts)
        elif kind == ActionType.HOLD:
            key = self._key.get().strip()
            action = Action(
                type=kind,
                key=key or None,
                button=MouseButton(self._button.get()) if not key else None,
                x=self._int(self._x) if not key else None,
                y=self._int(self._y) if not key else None,
                hold_ms=self._int(self._hold, 500),
            )
        else:
            action = Action(type=ActionType.DELAY, delay_ms=self._int(self._delay, 100))
        self.append_action(action)
        self._on_status(f"Added: {action.summary()}")

    def _sync_hold_mode(self) -> None:
        """For hold type, prefer key OR mouse fields to avoid mixed input."""
        if self._type.get() != ActionType.HOLD.value:
            return
        self._sync_form_visibility()

    def _sync_form_visibility(self) -> None:
        """Show only fields needed for the selected action type."""
        kind = self._type.get()
        self._hint.configure(text=TYPE_HINTS.get(kind, ""))
        visible: set[str] = set()
        if kind == ActionType.MOUSE_CLICK.value:
            visible = {"xy", "button", "phase"}
            self._phase.configure(values=["click", "down", "up"])
            if self._phase.get() not in ("click", "down", "up"):
                self._phase.set("click")
        elif kind == ActionType.MOUSE_MOVE.value:
            visible = {"xy"}
        elif kind == ActionType.KEY.value:
            visible = {"key", "phase"}
            self._phase.configure(values=["tap", "down", "up"])
            if self._phase.get() not in ("tap", "down", "up"):
                self._phase.set("tap")
        elif kind == ActionType.HOTKEY.value:
            visible = {"hotkeys"}
        elif kind == ActionType.HOLD.value:
            if self._key.get().strip():
                visible = {"key", "hold"}
            else:
                visible = {"key", "button", "xy", "hold"}
        elif kind == ActionType.DELAY.value:
            visible = {"delay"}

        for key, widgets in self._field_rows.items():
            for widget in widgets:
                if key in visible:
                    widget.grid()
                else:
                    widget.grid_remove()
