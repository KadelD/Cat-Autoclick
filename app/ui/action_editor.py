"""Action list and form for adding/editing macro steps."""

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

ChangedCallback = Callable[[], None]


class ActionEditor(ctk.CTkFrame):
    """Shows preset actions and a compact add form."""

    def __init__(self, master: ctk.CTkBaseClass, on_changed: ChangedCallback, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._on_changed = on_changed
        self._preset: Preset | None = None
        self._selected_index: int | None = None

        header = ctk.CTkLabel(self, text="Actions", font=ctk.CTkFont(size=16, weight="bold"))
        header.pack(anchor="w", padx=12, pady=(12, 4))

        self._list = ctk.CTkScrollableFrame(self, height=260)
        self._list.pack(fill="both", expand=True, padx=8, pady=4)

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(tools, text="Up", width=50, command=self._move_up).pack(side="left", padx=2)
        ctk.CTkButton(tools, text="Down", width=60, command=self._move_down).pack(side="left", padx=2)
        ctk.CTkButton(tools, text="Remove", width=70, command=self._remove).pack(side="left", padx=2)
        ctk.CTkButton(tools, text="Clear", width=60, command=self._clear).pack(side="left", padx=2)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=8, pady=(8, 12))
        ctk.CTkLabel(form, text="Add step", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4)
        )

        ctk.CTkLabel(form, text="Type").grid(row=1, column=0, sticky="w", padx=8)
        self._type = ctk.CTkOptionMenu(
            form,
            values=[t.value for t in ActionType],
            command=lambda _v: self._sync_form_visibility(),
        )
        self._type.set(ActionType.MOUSE_CLICK.value)
        self._type.grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        ctk.CTkLabel(form, text="X").grid(row=2, column=0, sticky="w", padx=8)
        self._x = ctk.CTkEntry(form, width=80)
        self._x.insert(0, "100")
        self._x.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(form, text="Y").grid(row=2, column=2, sticky="w", padx=8)
        self._y = ctk.CTkEntry(form, width=80)
        self._y.insert(0, "100")
        self._y.grid(row=2, column=3, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(form, text="Button").grid(row=3, column=0, sticky="w", padx=8)
        self._button = ctk.CTkOptionMenu(form, values=[b.value for b in MouseButton])
        self._button.set(MouseButton.LEFT.value)
        self._button.grid(row=3, column=1, sticky="ew", padx=4, pady=4)

        ctk.CTkLabel(form, text="Key").grid(row=3, column=2, sticky="w", padx=8)
        self._key = ctk.CTkEntry(form, width=100, placeholder_text="e.g. a / ctrl / f5")
        self._key.grid(row=3, column=3, sticky="ew", padx=4, pady=4)

        ctk.CTkLabel(form, text="Hotkeys").grid(row=4, column=0, sticky="w", padx=8)
        self._keys = ctk.CTkEntry(form, placeholder_text="ctrl+c")
        self._keys.grid(row=4, column=1, columnspan=3, sticky="ew", padx=4, pady=4)

        ctk.CTkLabel(form, text="Hold ms").grid(row=5, column=0, sticky="w", padx=8)
        self._hold = ctk.CTkEntry(form, width=80)
        self._hold.insert(0, "500")
        self._hold.grid(row=5, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(form, text="Delay ms").grid(row=5, column=2, sticky="w", padx=8)
        self._delay = ctk.CTkEntry(form, width=80)
        self._delay.insert(0, "100")
        self._delay.grid(row=5, column=3, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(form, text="Phase").grid(row=6, column=0, sticky="w", padx=8)
        self._phase = ctk.CTkOptionMenu(form, values=["click", "tap", "down", "up"])
        self._phase.set("click")
        self._phase.grid(row=6, column=1, sticky="ew", padx=4, pady=4)

        ctk.CTkButton(form, text="Add action", command=self._add).grid(
            row=6, column=2, columnspan=2, sticky="e", padx=8, pady=8
        )
        for col in range(4):
            form.grid_columnconfigure(col, weight=1)

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
            ctk.CTkLabel(self._list, text="Select or create a preset").pack(anchor="w", padx=6)
            return
        if not self._preset.actions:
            ctk.CTkLabel(self._list, text="No actions yet — record or add below").pack(
                anchor="w", padx=6
            )
            return
        for i, action in enumerate(self._preset.actions):
            selected = i == self._selected_index
            row = ctk.CTkFrame(
                self._list,
                fg_color=("#cfe2f3" if selected else ("gray90", "gray25")),
            )
            row.pack(fill="x", pady=2, padx=2)
            label = ctk.CTkLabel(
                row,
                text=f"{i + 1}. {action.summary()}",
                anchor="w",
            )
            label.pack(side="left", fill="x", expand=True, padx=8, pady=6)
            # Bind click on row/label
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
        action: Action
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
            phase_raw = self._phase.get()
            key_phase = KeyPhase.TAP
            if phase_raw == "down":
                key_phase = KeyPhase.DOWN
            elif phase_raw == "up":
                key_phase = KeyPhase.UP
            action = Action(
                type=kind,
                key=self._key.get().strip() or "a",
                key_phase=key_phase,
            )
        elif kind == ActionType.HOTKEY:
            parts = [p.strip() for p in self._keys.get().replace("+", " ").split() if p.strip()]
            if not parts:
                parts = ["ctrl", "c"]
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

    def _sync_form_visibility(self) -> None:
        # Kept simple: all fields always visible; labels guide usage.
        pass
