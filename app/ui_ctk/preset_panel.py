"""Left-side preset list with create / rename / delete / duplicate."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import customtkinter as ctk

from app.core.models import Preset
from app.ui_ctk import theme as T

SelectCallback = Callable[[Preset | None], None]
MutateCallback = Callable[[], None]


class PresetPanel(ctk.CTkFrame):
    """Scrollable preset picker and management buttons."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_select: SelectCallback,
        on_changed: MutateCallback,
        **kwargs,
    ) -> None:
        kwargs.setdefault("fg_color", T.PANEL)
        kwargs.setdefault("corner_radius", 14)
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._on_changed = on_changed
        self._presets: list[Preset] = []
        self._selected_id: str | None = None

        title = ctk.CTkLabel(
            self,
            text="Presets",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=T.CYAN,
        )
        title.pack(anchor="w", padx=14, pady=(14, 6))

        self._list = ctk.CTkScrollableFrame(
            self,
            width=220,
            fg_color=T.PANEL_ALT,
            corner_radius=10,
            scrollbar_button_color=T.NAVY,
            scrollbar_button_hover_color=T.PURPLE_DIM,
        )
        self._list.pack(fill="both", expand=True, padx=10, pady=4)
        self._buttons: dict[str, ctk.CTkButton] = {}

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=8)
        for text, cmd in (("New", self._new), ("Dup", self._dup), ("Del", self._del)):
            ctk.CTkButton(
                bar,
                text=text,
                width=58,
                height=30,
                fg_color=T.NAVY,
                hover_color=T.PURPLE_DIM,
                text_color=T.WHITE,
                command=cmd,
            ).pack(side="left", padx=3)

        rename_row = ctk.CTkFrame(self, fg_color="transparent")
        rename_row.pack(fill="x", padx=10, pady=(0, 12))
        self._rename_entry = ctk.CTkEntry(
            rename_row,
            placeholder_text="Rename…",
            fg_color=T.INPUT,
            border_color=T.BORDER,
            text_color=T.WHITE,
            placeholder_text_color=T.MUTED,
        )
        self._rename_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            rename_row,
            text="Rename",
            width=74,
            height=30,
            fg_color=T.PURPLE,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self._rename,
        ).pack(side="left")

    def set_presets(self, presets: list[Preset], selected_id: str | None = None) -> None:
        self._presets = list(presets)
        if selected_id is not None:
            self._selected_id = selected_id
        elif self._selected_id not in {p.id for p in self._presets}:
            self._selected_id = self._presets[0].id if self._presets else None
        self._render()

    @property
    def presets(self) -> list[Preset]:
        """Current in-memory preset list shared with the main window."""
        return self._presets

    def selected(self) -> Preset | None:
        for p in self._presets:
            if p.id == self._selected_id:
                return p
        return None

    def _render(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()
        self._buttons.clear()
        for preset in self._presets:
            is_sel = preset.id == self._selected_id
            btn = ctk.CTkButton(
                self._list,
                text=preset.name,
                anchor="w",
                height=34,
                fg_color=T.PURPLE if is_sel else T.BG,
                hover_color=T.PURPLE_DIM if is_sel else T.NAVY,
                text_color=T.WHITE,
                border_width=1,
                border_color=T.CYAN if is_sel else T.BORDER,
                command=lambda pid=preset.id: self._pick(pid),
            )
            btn.pack(fill="x", pady=3, padx=2)
            self._buttons[preset.id] = btn
            if is_sel:
                self._rename_entry.delete(0, "end")
                self._rename_entry.insert(0, preset.name)

    def _pick(self, preset_id: str) -> None:
        self._selected_id = preset_id
        self._render()
        self._on_select(self.selected())

    def _new(self) -> None:
        n = len(self._presets) + 1
        preset = Preset(name=f"Macro {n}")
        self._presets.append(preset)
        self._selected_id = preset.id
        self._on_changed()
        self._on_select(preset)
        self._render()

    def _dup(self) -> None:
        src = self.selected()
        if src is None:
            return
        clone = Preset.from_dict(src.to_dict())
        clone.id = uuid4().hex[:10]
        clone.name = f"{src.name} Copy"
        for action in clone.actions:
            action.id = uuid4().hex[:10]
        self._presets.append(clone)
        self._selected_id = clone.id
        self._on_changed()
        self._on_select(clone)
        self._render()

    def _del(self) -> None:
        cur = self.selected()
        if cur is None:
            return
        self._presets = [p for p in self._presets if p.id != cur.id]
        self._selected_id = self._presets[0].id if self._presets else None
        self._on_changed()
        self._on_select(self.selected())
        self._render()

    def _rename(self) -> None:
        cur = self.selected()
        if cur is None:
            return
        name = self._rename_entry.get().strip()
        if not name:
            return
        cur.name = name
        self._on_changed()
        self._render()
