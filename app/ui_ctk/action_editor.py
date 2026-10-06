"""Action list and type-aware add-step form in a side-by-side layout."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from app.core.models import (
    Action,
    ActionType,
    ClickPhase,
    KeyPhase,
    MouseButton,
    OnFail,
    Preset,
)
from app.core.monitors import list_monitors
from app.core.vision import templates_dir
from app.ui_ctk import theme as T
from app.ui_ctk.action_display import row_style
from app.ui_ctk.icons import glyph, material_font
from app.ui_ctk.region_picker import pick_region
from app.ui_ctk.tooltip import HoverTip

ChangedCallback = Callable[[], None]
StatusCallback = Callable[[str], None]

# Friendly English labels shown in the type dropdown (order preserved).
TYPE_LABELS: list[tuple[str, ActionType]] = [
    ("Mouse click", ActionType.MOUSE_CLICK),
    ("Move cursor", ActionType.MOUSE_MOVE),
    ("Drag mouse", ActionType.MOUSE_DRAG),
    ("Press key", ActionType.KEY),
    ("Hotkey chord", ActionType.HOTKEY),
    ("Hold key / mouse", ActionType.HOLD),
    ("Wait (delay)", ActionType.DELAY),
    ("Find text & click", ActionType.FIND_TEXT),
    ("Find image & click", ActionType.FIND_IMAGE),
    ("Wait for text", ActionType.WAIT_TEXT),
    ("Wait for image", ActionType.WAIT_IMAGE),
    ("If text found", ActionType.IF_TEXT),
    ("If image found", ActionType.IF_IMAGE),
    ("Else", ActionType.ELSE),
    ("End if", ActionType.ENDIF),
]
LABEL_TO_TYPE = {label: kind for label, kind in TYPE_LABELS}
TYPE_TO_LABEL = {kind: label for label, kind in TYPE_LABELS}

TYPE_HINTS = {
    ActionType.MOUSE_CLICK: "Set X/Y, mouse button, and click phase.",
    ActionType.MOUSE_MOVE: "Move the cursor to X/Y on the selected monitor.",
    ActionType.MOUSE_DRAG: "Drag from X/Y to End X/Y over Hold ms at constant speed.",
    ActionType.KEY: "Single key — tap, press, or release.",
    ActionType.HOTKEY: "Chord like ctrl+c or ctrl+shift+s.",
    ActionType.HOLD: "Fill Key OR mouse Button + X/Y (not both).",
    ActionType.DELAY: "Wait a fixed number of milliseconds.",
    ActionType.FIND_TEXT: "OCR find text (Thai/English) then click. Optional capture region.",
    ActionType.FIND_IMAGE: "Find a template image then click. Use Browse and optional region.",
    ActionType.WAIT_TEXT: "Wait until text appears, or until timeout.",
    ActionType.WAIT_IMAGE: "Wait until an image appears, or until timeout.",
    ActionType.IF_TEXT: "Branch if text is found. Close with Else / End if.",
    ActionType.IF_IMAGE: "Branch if image is found. Close with Else / End if.",
    ActionType.ELSE: "Else branch of the nearest open If.",
    ActionType.ENDIF: "Close the nearest open If block.",
}

VISION_TYPES = {
    ActionType.FIND_TEXT,
    ActionType.FIND_IMAGE,
    ActionType.WAIT_TEXT,
    ActionType.WAIT_IMAGE,
    ActionType.IF_TEXT,
    ActionType.IF_IMAGE,
}

OCR_TYPES = {
    ActionType.FIND_TEXT,
    ActionType.WAIT_TEXT,
    ActionType.IF_TEXT,
}

PHASE_CLICK = {"Click": "click", "Press": "down", "Release": "up"}
PHASE_KEY = {"Tap": "tap", "Press": "down", "Release": "up"}
BUTTON_LABELS = {"Left": "left", "Right": "right", "Middle": "middle"}
ON_FAIL_LABELS = {"Stop": "stop", "Continue": "continue"}
CLICK_PHASE_LABEL = {v: k for k, v in PHASE_CLICK.items()}
KEY_PHASE_LABEL = {v: k for k, v in PHASE_KEY.items()}
BUTTON_VALUE_LABEL = {v: k for k, v in BUTTON_LABELS.items()}
ON_FAIL_VALUE_LABEL = {v: k for k, v in ON_FAIL_LABELS.items()}


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
        self._drag_index: int | None = None
        self._drag_start_xy: tuple[int, int] | None = None
        self._drag_hover: int | None = None
        self._row_widgets: list[ctk.CTkFrame] = []
        self._row_labels: list[ctk.CTkLabel] = []
        self._row_tips: list[HoverTip | None] = []
        self._row_info: list[ctk.CTkLabel | None] = []
        self._empty_label: ctk.CTkLabel | None = None
        self._render_job: str | None = None
        self._ocr_enabled = True

        self.grid_columnconfigure(0, weight=3, minsize=280)
        self.grid_columnconfigure(1, weight=2, minsize=280)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1, minsize=180)

        ctk.CTkLabel(
            left,
            text="Actions",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=T.WHITE,
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 2))
        ctk.CTkLabel(
            left,
            text="Click to edit · empty / Cancel / Esc to leave",
            font=ctk.CTkFont(size=11),
            text_color=T.MUTED,
        ).grid(row=0, column=0, sticky="e", padx=4, pady=(0, 2))

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
        # Up/Down hidden — reorder via drag handles (keeps the bar uncluttered).
        for text, cmd in (
            ("Remove", self._remove),
            ("Clear", self._clear),
        ):
            ctk.CTkButton(
                tools,
                text=text,
                width=80,
                height=30,
                fg_color=T.NAVY,
                hover_color=T.PURPLE_DIM,
                text_color=T.WHITE,
                command=cmd,
            ).pack(side="left", padx=3)

        form_wrap = ctk.CTkFrame(self, fg_color=T.PANEL_ALT, corner_radius=12)
        form_wrap.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        form_wrap.grid_columnconfigure(0, weight=1)
        form_wrap.grid_rowconfigure(1, weight=1)

        self._form_title = ctk.CTkLabel(
            form_wrap,
            text="Add step",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=T.CYAN,
            height=28,
            anchor="w",
        )
        self._form_title.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))

        self._form = ctk.CTkScrollableFrame(
            form_wrap,
            fg_color="transparent",
            scrollbar_button_color=T.NAVY,
            scrollbar_button_hover_color=T.CYAN_DIM,
        )
        self._form.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self._form.grid_columnconfigure(0, weight=1)

        self._hint = ctk.CTkLabel(
            self._form,
            text=TYPE_HINTS[ActionType.MOUSE_CLICK],
            text_color=T.MUTED,
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left",
            wraplength=260,
        )
        self._hint.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 6))

        ctk.CTkLabel(self._form, text="Step type", text_color=T.MUTED).grid(
            row=1, column=0, sticky="w", padx=8, pady=(4, 2)
        )
        self._type = ctk.CTkOptionMenu(
            self._form,
            values=self._type_label_values(),
            command=lambda _v: self._sync_form_visibility(),
            height=36,
            fg_color=T.NAVY,
            button_color=T.PURPLE_DIM,
            button_hover_color=T.PURPLE,
            dropdown_fg_color=T.PANEL,
            dropdown_hover_color=T.NAVY,
            text_color=T.WHITE,
            dynamic_resizing=False,
        )
        self._type.set(TYPE_TO_LABEL[ActionType.MOUSE_CLICK])
        self._type.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))

        # Field host uses 2 columns for compact labeled inputs.
        self._fields = ctk.CTkFrame(self._form, fg_color="transparent")
        self._fields.grid(row=3, column=0, sticky="ew")
        self._fields.grid_columnconfigure(1, weight=1)

        self._x = self._labeled_entry(0, "X", "100", key="xy")
        self._y = self._labeled_entry(1, "Y", "100", key="xy")
        self._end_x = self._labeled_entry(2, "End X", "200", key="end_xy")
        self._end_y = self._labeled_entry(3, "End Y", "200", key="end_xy")
        self._button = self._labeled_option(
            4, "Button", list(BUTTON_LABELS.keys()), "Left", key="button"
        )
        self._key = self._labeled_entry(5, "Key", "", placeholder="a / ctrl / f5", key="key")
        self._key.bind("<KeyRelease>", lambda _e: self._sync_hold_mode())
        self._keys = self._labeled_entry(6, "Hotkeys", "", placeholder="ctrl+c", key="hotkeys")
        self._hold = self._labeled_entry(7, "Hold ms", "500", key="hold")
        self._delay = self._labeled_entry(8, "Delay ms", "100", key="delay")
        self._phase = self._labeled_option(
            9, "Phase", list(PHASE_CLICK.keys()), "Click", key="phase"
        )
        self._query = self._labeled_entry(
            10, "Text", "", placeholder="Thai or English text", key="query"
        )
        self._image = self._labeled_entry(
            11, "Image", "", placeholder="button.png", key="image"
        )
        browse_lbl = ctk.CTkLabel(self._fields, text="", text_color=T.MUTED)
        browse_lbl.grid(row=12, column=0, sticky="w", padx=8, pady=2)
        self._browse_btn = ctk.CTkButton(
            self._fields,
            text="Browse…",
            width=100,
            height=28,
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            command=self._browse_template,
        )
        self._browse_btn.grid(row=12, column=1, sticky="w", padx=4, pady=2)
        self._field_rows.setdefault("image", []).extend([browse_lbl, self._browse_btn])

        self._threshold = self._labeled_entry(13, "Threshold", "0.85", key="threshold")
        self._timeout = self._labeled_entry(14, "Timeout ms", "5000", key="timeout")
        self._on_fail = self._labeled_option(
            15, "On fail", list(ON_FAIL_LABELS.keys()), "Stop", key="on_fail"
        )

        monitor_values = ["Preset monitor"] + [f"Monitor {m.index}" for m in list_monitors()]
        self._cap_mon = self._labeled_option(
            16, "Capture on", monitor_values, "Preset monitor", key="capture"
        )
        self._rx = self._labeled_entry(17, "Region X", "0", key="capture")
        self._ry = self._labeled_entry(18, "Region Y", "0", key="capture")
        self._rw = self._labeled_entry(19, "Region W", "0", placeholder="0 = full", key="capture")
        self._rh = self._labeled_entry(20, "Region H", "0", placeholder="0 = full", key="capture")
        pick_lbl = ctk.CTkLabel(self._fields, text="Region", text_color=T.MUTED)
        pick_lbl.grid(row=21, column=0, sticky="w", padx=8, pady=4)
        pick_row = ctk.CTkFrame(self._fields, fg_color="transparent")
        pick_row.grid(row=21, column=1, sticky="ew", padx=4, pady=4)
        self._pick_btn = ctk.CTkButton(
            pick_row,
            text="Pick…",
            width=70,
            height=28,
            fg_color=T.CYAN_DIM,
            hover_color=T.CYAN,
            text_color=T.BG,
            command=self._pick_region,
        )
        self._pick_btn.pack(side="left", padx=(0, 4))
        self._clear_region_btn = ctk.CTkButton(
            pick_row,
            text="Full",
            width=60,
            height=28,
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            command=self._clear_region,
        )
        self._clear_region_btn.pack(side="left")
        self._field_rows.setdefault("capture", []).extend([pick_lbl, pick_row])

        btn_row = ctk.CTkFrame(form_wrap, fg_color="transparent", height=36)
        btn_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))
        btn_row.grid_propagate(False)
        btn_row.grid_columnconfigure(0, weight=1, uniform="editbtns")
        btn_row.grid_columnconfigure(1, weight=1, uniform="editbtns")
        self._btn_row = btn_row
        self._btn_cancel = ctk.CTkButton(
            btn_row,
            text="Cancel",
            height=36,
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self._cancel_edit,
        )
        self._btn_update = ctk.CTkButton(
            btn_row,
            text="Save changes",
            height=36,
            fg_color=T.CYAN_DIM,
            hover_color=T.CYAN,
            text_color=T.BG,
            command=self._update,
        )
        self._btn_add = ctk.CTkButton(
            btn_row,
            text="Add action",
            height=36,
            fg_color=T.PURPLE,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self._add,
        )

        self._sync_form_visibility()
        self._sync_edit_chrome()
        # Escape on the root window (CTk forbids widget.bind_all).
        self.winfo_toplevel().bind("<Escape>", self._on_escape, add="+")
        self._list.bind("<Button-1>", self._on_list_background_click, add="+")
        try:
            self._list._parent_canvas.bind(
                "<Button-1>", self._on_list_background_click, add="+"
            )
        except Exception:
            pass

    def destroy(self) -> None:
        """Drop Escape binding when the editor is destroyed."""
        try:
            self.winfo_toplevel().unbind("<Escape>")
        except Exception:
            pass
        super().destroy()

    def _type_label_values(self) -> list[str]:
        """Dropdown labels; OCR types omitted when OCR is disabled."""
        return [
            label
            for label, kind in TYPE_LABELS
            if self._ocr_enabled or kind not in OCR_TYPES
        ]

    def set_ocr_enabled(self, enabled: bool) -> None:
        """Show or hide OCR step types in the Add/Edit dropdown."""
        self._ocr_enabled = bool(enabled)
        self._refresh_type_menu()

    def _refresh_type_menu(self, *, keep: ActionType | None = None) -> None:
        """Rebuild type dropdown; optionally keep an OCR type visible for edit."""
        values = self._type_label_values()
        if keep is not None and keep in OCR_TYPES:
            label = TYPE_TO_LABEL.get(keep)
            if label and label not in values:
                # Preserve order: insert near other vision labels.
                values = list(values)
                # Place before first image vision label if present.
                insert_at = len(values)
                for i, v in enumerate(values):
                    if LABEL_TO_TYPE.get(v) in (
                        ActionType.FIND_IMAGE,
                        ActionType.WAIT_IMAGE,
                        ActionType.IF_IMAGE,
                    ):
                        insert_at = i
                        break
                values.insert(insert_at, label)
        current = self._type.get()
        self._type.configure(values=values)
        if current not in values:
            self._type.set(TYPE_TO_LABEL[ActionType.MOUSE_CLICK])
            self._sync_form_visibility()

    def _selected_type(self) -> ActionType:
        """Map the friendly dropdown label to an ActionType."""
        return LABEL_TO_TYPE.get(self._type.get(), ActionType.MOUSE_CLICK)

    def _labeled_entry(
        self,
        row: int,
        label: str,
        value: str,
        *,
        placeholder: str = "",
        key: str,
    ) -> ctk.CTkEntry:
        lbl = ctk.CTkLabel(self._fields, text=label, text_color=T.MUTED)
        lbl.grid(row=row, column=0, sticky="w", padx=8, pady=4)
        entry = ctk.CTkEntry(
            self._fields,
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
        lbl = ctk.CTkLabel(self._fields, text=label, text_color=T.MUTED)
        lbl.grid(row=row, column=0, sticky="w", padx=8, pady=4)
        menu = ctk.CTkOptionMenu(
            self._fields,
            values=values,
            height=32,
            fg_color=T.NAVY,
            button_color=T.PURPLE_DIM,
            button_hover_color=T.PURPLE,
            dropdown_fg_color=T.PANEL,
            dropdown_hover_color=T.NAVY,
            text_color=T.WHITE,
            dynamic_resizing=False,
        )
        menu.set(default)
        menu.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        self._field_rows.setdefault(key, []).extend([lbl, menu])
        return menu

    def _browse_template(self) -> None:
        """Pick an image and copy it into templates/ for portable presets."""
        path = filedialog.askopenfilename(
            title="Select template image",
            filetypes=[
                ("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        src = Path(path)
        dest_dir = templates_dir()
        dest = dest_dir / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        self._image.delete(0, "end")
        self._image.insert(0, dest.name)
        self._on_status(f"Template saved: {dest.name}")

    def _resolved_capture_monitor(self) -> int:
        """Monitor index used for Pick region (capture override or preset)."""
        raw = self._cap_mon.get()
        if raw.startswith("Preset"):
            return self._preset.monitor_index if self._preset else 0
        try:
            return int(raw.replace("Monitor", "").strip())
        except ValueError:
            return 0

    def _pick_region(self) -> None:
        """Drag-select a capture rectangle on the chosen monitor."""
        mon = self._resolved_capture_monitor()

        def on_done(x: int, y: int, w: int, h: int) -> None:
            for entry, value in (
                (self._rx, x),
                (self._ry, y),
                (self._rw, w),
                (self._rh, h),
            ):
                entry.delete(0, "end")
                entry.insert(0, str(value))
            self._on_status(f"Capture region: {x},{y} {w}x{h} on monitor {mon}")

        pick_region(self.winfo_toplevel(), mon, on_done=on_done)

    def _clear_region(self) -> None:
        """Reset region fields to full-monitor capture."""
        for entry in (self._rx, self._ry, self._rw, self._rh):
            entry.delete(0, "end")
            entry.insert(0, "0")
        self._on_status("Capture region: full monitor")

    def _capture_fields(self) -> dict:
        """Read capture monitor/region for vision actions."""
        raw = self._cap_mon.get()
        capture_monitor = None if raw.startswith("Preset") else self._resolved_capture_monitor()
        return {
            "capture_monitor": capture_monitor,
            "region_x": self._int(self._rx, 0),
            "region_y": self._int(self._ry, 0),
            "region_w": self._int(self._rw, 0),
            "region_h": self._int(self._rh, 0),
        }

    def set_preset(self, preset: Preset | None) -> None:
        self._preset = preset
        self._selected_index = None
        self._render()
        self._reset_form_defaults()
        self._sync_edit_chrome()

    def append_action(self, action: Action) -> None:
        """Append one action and add a single row (no full list rebuild)."""
        if self._preset is None:
            return
        self._clear_empty_state()
        self._preset.actions.append(action)
        self._append_row(len(self._preset.actions) - 1, action)
        self._on_changed()

    def _set_entry(self, entry: ctk.CTkEntry, value: object) -> None:
        """Replace entry text."""
        entry.delete(0, "end")
        if value is None:
            return
        text = str(value)
        if text:
            entry.insert(0, text)

    def _sync_edit_chrome(self) -> None:
        """Swap Add vs Cancel/Save inside a fixed-height button row (no layout jump)."""
        editing = self._selected_index is not None
        self._btn_cancel.grid_forget()
        self._btn_update.grid_forget()
        self._btn_add.grid_forget()

        if editing:
            self._form_title.configure(text=f"Edit step {self._selected_index + 1}")
            self._btn_cancel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            self._btn_update.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        else:
            self._form_title.configure(text="Add step")
            # Same two-column footprint as Cancel|Save so the panel width/height stay put.
            self._btn_add.grid(row=0, column=0, columnspan=2, sticky="nsew")

    def _reset_form_defaults(self) -> None:
        """Restore the add-step form to blank defaults (leave edit mode)."""
        self._type.set(TYPE_TO_LABEL[ActionType.MOUSE_CLICK])
        self._sync_form_visibility()
        self._set_entry(self._x, 100)
        self._set_entry(self._y, 100)
        self._set_entry(self._end_x, 200)
        self._set_entry(self._end_y, 200)
        self._button.set("Left")
        self._set_entry(self._key, "")
        self._set_entry(self._keys, "")
        self._set_entry(self._hold, 500)
        self._set_entry(self._delay, 100)
        self._phase.configure(values=list(PHASE_CLICK.keys()))
        self._phase.set("Click")
        self._set_entry(self._query, "")
        self._set_entry(self._image, "")
        self._set_entry(self._threshold, 0.85)
        self._set_entry(self._timeout, 5000)
        self._on_fail.set("Stop")
        self._cap_mon.set("Preset monitor")
        self._set_entry(self._rx, 0)
        self._set_entry(self._ry, 0)
        self._set_entry(self._rw, 0)
        self._set_entry(self._rh, 0)

    def _cancel_edit(self) -> None:
        """Exit edit mode without saving; return to Add step."""
        if self._selected_index is None:
            return
        self._selected_index = None
        self._refresh_selection_styles()
        self._reset_form_defaults()
        self._sync_edit_chrome()
        self._on_status("Edit cancelled")

    def _on_escape(self, event=None) -> str | None:
        """Esc leaves the current edit selection (main window only)."""
        if self._selected_index is None:
            return None
        try:
            if event is not None and event.widget.winfo_toplevel() is not self.winfo_toplevel():
                return None
        except Exception:
            return None
        self._cancel_edit()
        return "break"

    def _on_list_background_click(self, event) -> None:
        """Click empty list space to leave edit mode."""
        if self._selected_index is None:
            return
        if self._index_at_pointer(event) is None:
            self._cancel_edit()

    def _load_action_into_form(self, action: Action) -> None:
        """Fill the right-hand form from an existing action for editing."""
        self._refresh_type_menu(keep=action.type)
        label = TYPE_TO_LABEL.get(action.type)
        if label:
            self._type.set(label)
        self._sync_form_visibility()

        self._set_entry(self._x, action.x if action.x is not None else "")
        self._set_entry(self._y, action.y if action.y is not None else "")
        self._set_entry(self._end_x, action.end_x if action.end_x is not None else "")
        self._set_entry(self._end_y, action.end_y if action.end_y is not None else "")
        if action.button is not None:
            self._button.set(BUTTON_VALUE_LABEL.get(action.button.value, "Left"))
        self._set_entry(self._key, action.key or "")
        self._set_entry(self._keys, "+".join(action.keys) if action.keys else "")
        self._set_entry(self._hold, action.hold_ms if action.hold_ms else "")
        self._set_entry(self._delay, action.delay_ms)
        if action.type == ActionType.KEY:
            self._phase.configure(values=list(PHASE_KEY.keys()))
            self._phase.set(KEY_PHASE_LABEL.get(action.key_phase.value, "Tap"))
        elif action.type == ActionType.MOUSE_CLICK:
            self._phase.configure(values=list(PHASE_CLICK.keys()))
            self._phase.set(CLICK_PHASE_LABEL.get(action.click_phase.value, "Click"))
        self._set_entry(self._query, action.query)
        self._set_entry(self._image, action.image_path)
        self._set_entry(self._threshold, action.threshold)
        self._set_entry(self._timeout, action.timeout_ms)
        self._on_fail.set(ON_FAIL_VALUE_LABEL.get(action.on_fail.value, "Stop"))
        if action.capture_monitor is None:
            self._cap_mon.set("Preset monitor")
        else:
            self._cap_mon.set(f"Monitor {action.capture_monitor}")
        self._set_entry(self._rx, action.region_x)
        self._set_entry(self._ry, action.region_y)
        self._set_entry(self._rw, action.region_w)
        self._set_entry(self._rh, action.region_h)
        self._sync_hold_mode()
        self._sync_edit_chrome()

    def _clear_empty_state(self) -> None:
        if self._empty_label is not None:
            self._empty_label.destroy()
            self._empty_label = None

    def _show_empty_state(self, text: str) -> None:
        self._clear_empty_state()
        self._empty_label = ctk.CTkLabel(self._list, text=text, text_color=T.MUTED)
        self._empty_label.pack(anchor="w", padx=8, pady=8)

    def _render(self) -> None:
        """Full rebuild — used when switching presets or after structural edits."""
        for child in self._list.winfo_children():
            child.destroy()
        self._row_widgets.clear()
        self._row_labels.clear()
        self._row_tips.clear()
        self._row_info.clear()
        self._empty_label = None
        if self._preset is None:
            self._show_empty_state("Select or create a preset")
            return
        if not self._preset.actions:
            self._show_empty_state("No actions yet — record or add a step on the right")
            return
        for i, action in enumerate(self._preset.actions):
            self._append_row(i, action)

    def _append_row(self, index: int, action: Action) -> None:
        """Create one styled row and pack it at the end."""
        style = row_style(action)
        selected = index == self._selected_index
        pad_y = 2 if style.compact else 5
        row = ctk.CTkFrame(
            self._list,
            fg_color=T.PURPLE_DIM if selected else T.BG,
            corner_radius=8,
            border_width=1,
            border_color=T.CYAN if selected else T.BORDER,
            cursor="hand2",
            height=26 if style.compact else 40,
        )
        row.pack(fill="x", pady=(1 if style.compact else 3), padx=2)
        row.pack_propagate(False)
        handle = ctk.CTkLabel(
            row,
            text=glyph("drag_indicator", "⠿"),
            width=22,
            text_color=T.MUTED,
            font=material_font(14 if style.compact else 16),
        )
        handle.pack(side="left", padx=(4, 0), pady=pad_y)
        icon = ctk.CTkLabel(
            row,
            text=glyph(style.icon),
            width=28,
            text_color=style.accent,
            font=material_font(16 if style.compact else 20),
        )
        icon.pack(side="left", padx=(2, 0), pady=pad_y)
        key_size = 11 if style.compact else (18 if style.emphasize else 13)
        label = ctk.CTkLabel(
            row,
            text=style.text,
            anchor="w",
            text_color=style.accent if (style.compact or style.emphasize) else T.WHITE,
            font=ctk.CTkFont(size=key_size, weight="bold" if style.emphasize else "normal"),
        )
        label.pack(side="left", padx=(4, 2), pady=pad_y)
        tip: HoverTip | None = None
        info: ctk.CTkLabel | None = None
        bind_widgets: list[ctk.CTkBaseClass] = [row, handle, icon, label]
        if style.detail:
            # Coordinates / extras stay behind the info icon until hover.
            info = ctk.CTkLabel(
                row,
                text=glyph("info", "!"),
                width=22,
                height=22,
                corner_radius=11,
                fg_color=T.NAVY,
                text_color=T.CYAN,
                font=material_font(14),
                cursor="question_arrow",
            )
            info.pack(side="left", padx=(4, 6), pady=pad_y)
            tip = HoverTip(info, style.detail)
        spacer = ctk.CTkLabel(row, text="", text_color=T.MUTED)
        spacer.pack(side="left", fill="x", expand=True)
        bind_widgets_drag = bind_widgets + [spacer]
        self._bind_row_drag(bind_widgets_drag, index, skip_info=info)
        self._row_widgets.append(row)
        self._row_labels.append(label)
        self._row_tips.append(tip)
        self._row_info.append(info)

    def _bind_row_drag(
        self,
        widgets: list[ctk.CTkBaseClass],
        index: int,
        *,
        skip_info: ctk.CTkLabel | None,
    ) -> None:
        """Bind drag once; later refreshes only update `_cat_index` (no rebind)."""
        for widget in widgets:
            if skip_info is not None and widget == skip_info:
                continue
            widget._cat_index = index  # type: ignore[attr-defined]
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_motion)
            widget.bind("<ButtonRelease-1>", self._drag_end)

    def _index_from_event(self, event) -> int | None:
        """Resolve row index from the widget that received the event."""
        widget = event.widget
        for _ in range(10):
            idx = getattr(widget, "_cat_index", None)
            if isinstance(idx, int):
                return idx
            widget = getattr(widget, "master", None)
            if widget is None:
                break
        return None

    def _sync_row_indices(self) -> None:
        """Update stored indices after reorder — does not rebind events."""
        for i, row in enumerate(self._row_widgets):
            row._cat_index = i  # type: ignore[attr-defined]
            info = self._row_info[i] if i < len(self._row_info) else None
            for child in row.winfo_children():
                if info is not None and child == info:
                    continue
                child._cat_index = i  # type: ignore[attr-defined]

    def _refresh_selection_styles(self) -> None:
        """Update selection colors only (cheap path for click/cancel)."""
        for i, row in enumerate(self._row_widgets):
            selected = i == self._selected_index
            row.configure(
                fg_color=T.PURPLE_DIM if selected else T.BG,
                border_color=T.CYAN if selected else T.BORDER,
            )

    def _refresh_row_indices(self) -> None:
        """Sync indices + selection after reorder (no event rebinding)."""
        self._sync_row_indices()
        if self._preset is None:
            self._refresh_selection_styles()
            return
        for i, (label, action) in enumerate(
            zip(self._row_labels, self._preset.actions, strict=False)
        ):
            style = row_style(action)
            label.configure(text=style.text)
            tip = self._row_tips[i] if i < len(self._row_tips) else None
            if tip is not None:
                tip.set_text(style.detail or "")
        self._refresh_selection_styles()

    def _repack_rows(self) -> None:
        """Reorder packed rows to match action list without destroying widgets."""
        for row in self._row_widgets:
            row.pack_forget()
        for i, row in enumerate(self._row_widgets):
            compact = False
            if self._preset and i < len(self._preset.actions):
                compact = row_style(self._preset.actions[i]).compact
            row.pack(fill="x", pady=(1 if compact else 3), padx=2)
        self._refresh_row_indices()

    def _drag_start(self, event) -> None:
        """Begin dragging an action row without rebuilding the list."""
        index = self._index_from_event(event)
        if index is None:
            return
        self._drag_index = index
        self._drag_hover = None
        self._drag_start_xy = (int(event.x_root), int(event.y_root))
        prev = self._selected_index
        self._selected_index = index
        if prev is not None and prev != index and 0 <= prev < len(self._row_widgets):
            self._row_widgets[prev].configure(fg_color=T.BG, border_color=T.BORDER)
        self._row_widgets[index].configure(
            border_color=T.PURPLE,
            fg_color=T.PURPLE_DIM,
        )

    def _drag_motion(self, event) -> None:
        """Highlight only the drop target that changed (avoids O(n) configures)."""
        if self._drag_index is None:
            return
        if self._drag_start_xy is not None:
            if (
                abs(int(event.x_root) - self._drag_start_xy[0]) < 8
                and abs(int(event.y_root) - self._drag_start_xy[1]) < 8
            ):
                return
        target = self._index_at_pointer(event)
        if target == self._drag_hover:
            return
        old = self._drag_hover
        self._drag_hover = target
        if old is not None and old != self._drag_index and 0 <= old < len(self._row_widgets):
            self._row_widgets[old].configure(
                border_color=T.CYAN if old == self._selected_index else T.BORDER
            )
        if (
            target is not None
            and target != self._drag_index
            and 0 <= target < len(self._row_widgets)
        ):
            self._row_widgets[target].configure(border_color=T.CYAN)

    def _drag_end(self, event) -> None:
        """Reorder by repacking rows — avoids full destroy/rebuild flicker."""
        if self._preset is None or self._drag_index is None:
            return
        source = self._drag_index
        self._drag_index = None
        self._drag_hover = None
        start = self._drag_start_xy
        self._drag_start_xy = None
        moved = False
        if start is not None:
            try:
                moved = (
                    abs(int(event.x_root) - start[0]) >= 8
                    or abs(int(event.y_root) - start[1]) >= 8
                )
            except Exception:
                moved = False
        target = self._index_at_pointer(event) if moved else source
        if target is None or target == source:
            self._select(source)
            return
        acts = self._preset.actions
        item = acts.pop(source)
        acts.insert(target, item)
        row = self._row_widgets.pop(source)
        self._row_widgets.insert(target, row)
        label = self._row_labels.pop(source)
        self._row_labels.insert(target, label)
        tip = self._row_tips.pop(source)
        self._row_tips.insert(target, tip)
        info = self._row_info.pop(source)
        self._row_info.insert(target, info)
        self._selected_index = target
        self._repack_rows()
        self._load_action_into_form(item)
        self._on_changed()
        self._on_status(f"Moved step to position {target + 1}")

    def _index_at_pointer(self, event) -> int | None:
        """Find which action row is under the pointer."""
        try:
            root_x = event.x_root
            root_y = event.y_root
        except Exception:
            return None
        for i, row in enumerate(self._row_widgets):
            try:
                x = row.winfo_rootx()
                y = row.winfo_rooty()
                w = row.winfo_width()
                h = row.winfo_height()
            except Exception:
                continue
            if x <= root_x <= x + w and y <= root_y <= y + h:
                return i
        if self._row_widgets:
            last = self._row_widgets[-1]
            try:
                if root_y > last.winfo_rooty() + last.winfo_height():
                    return len(self._row_widgets) - 1
            except Exception:
                pass
        return None

    def _select(self, index: int) -> None:
        """Select a row and load it into the edit form."""
        self._selected_index = index
        self._refresh_selection_styles()
        if self._preset is None or index < 0 or index >= len(self._preset.actions):
            self._sync_edit_chrome()
            return
        self._load_action_into_form(self._preset.actions[index])
        self._on_status(f"Editing step {index + 1}")

    def _move_up(self) -> None:
        if self._preset is None or self._selected_index is None or self._selected_index <= 0:
            return
        i = self._selected_index
        acts = self._preset.actions
        acts[i - 1], acts[i] = acts[i], acts[i - 1]
        self._row_widgets[i - 1], self._row_widgets[i] = self._row_widgets[i], self._row_widgets[i - 1]
        self._row_labels[i - 1], self._row_labels[i] = self._row_labels[i], self._row_labels[i - 1]
        self._row_tips[i - 1], self._row_tips[i] = self._row_tips[i], self._row_tips[i - 1]
        self._row_info[i - 1], self._row_info[i] = self._row_info[i], self._row_info[i - 1]
        self._selected_index = i - 1
        self._repack_rows()
        self._load_action_into_form(acts[self._selected_index])
        self._on_changed()

    def _move_down(self) -> None:
        if self._preset is None or self._selected_index is None:
            return
        i = self._selected_index
        if i >= len(self._preset.actions) - 1:
            return
        acts = self._preset.actions
        acts[i + 1], acts[i] = acts[i], acts[i + 1]
        self._row_widgets[i + 1], self._row_widgets[i] = self._row_widgets[i], self._row_widgets[i + 1]
        self._row_labels[i + 1], self._row_labels[i] = self._row_labels[i], self._row_labels[i + 1]
        self._row_tips[i + 1], self._row_tips[i] = self._row_tips[i], self._row_tips[i + 1]
        self._row_info[i + 1], self._row_info[i] = self._row_info[i], self._row_info[i + 1]
        self._selected_index = i + 1
        self._repack_rows()
        self._load_action_into_form(acts[self._selected_index])
        self._on_changed()

    def _remove(self) -> None:
        if self._preset is None or self._selected_index is None:
            return
        i = self._selected_index
        del self._preset.actions[i]
        row = self._row_widgets.pop(i)
        self._row_labels.pop(i)
        self._row_tips.pop(i)
        self._row_info.pop(i)
        row.destroy()
        if not self._preset.actions:
            self._selected_index = None
            self._show_empty_state("No actions yet — record or add a step on the right")
            self._sync_edit_chrome()
        else:
            self._selected_index = min(i, len(self._preset.actions) - 1)
            self._refresh_row_indices()
            self._load_action_into_form(self._preset.actions[self._selected_index])
        self._on_changed()

    def _clear(self) -> None:
        if self._preset is None:
            return
        self._preset.actions.clear()
        self._selected_index = None
        self._render()
        self._sync_edit_chrome()
        self._on_changed()

    def _int(self, entry: ctk.CTkEntry, default: int = 0) -> int:
        try:
            return int(entry.get().strip())
        except ValueError:
            return default

    def _float(self, entry: ctk.CTkEntry, default: float = 0.85) -> float:
        try:
            return float(entry.get().strip())
        except ValueError:
            return default

    def _build_action_from_form(self) -> Action | None:
        """Create an Action from the current form fields, or None if invalid."""
        kind = self._selected_type()
        if kind == ActionType.MOUSE_CLICK:
            phase_raw = PHASE_CLICK.get(self._phase.get(), "click")
            return Action(
                type=kind,
                x=self._int(self._x),
                y=self._int(self._y),
                button=MouseButton(BUTTON_LABELS[self._button.get()]),
                click_phase=ClickPhase(phase_raw),
            )
        if kind == ActionType.MOUSE_MOVE:
            return Action(type=kind, x=self._int(self._x), y=self._int(self._y))
        if kind == ActionType.MOUSE_DRAG:
            return Action(
                type=kind,
                x=self._int(self._x),
                y=self._int(self._y),
                end_x=self._int(self._end_x),
                end_y=self._int(self._end_y),
                button=MouseButton(BUTTON_LABELS[self._button.get()]),
                hold_ms=max(1, self._int(self._hold, 500)),
                delay_ms=0,
            )
        if kind == ActionType.KEY:
            key = self._key.get().strip()
            if not key:
                self._on_status("Enter a key name first")
                return None
            phase_raw = PHASE_KEY.get(self._phase.get(), "tap")
            return Action(type=kind, key=key, key_phase=KeyPhase(phase_raw))
        if kind == ActionType.HOTKEY:
            parts = [p.strip() for p in self._keys.get().replace("+", " ").split() if p.strip()]
            if not parts:
                self._on_status("Enter a hotkey like ctrl+c")
                return None
            return Action(type=kind, keys=parts)
        if kind == ActionType.HOLD:
            key = self._key.get().strip()
            return Action(
                type=kind,
                key=key or None,
                button=MouseButton(BUTTON_LABELS[self._button.get()]) if not key else None,
                x=self._int(self._x) if not key else None,
                y=self._int(self._y) if not key else None,
                hold_ms=self._int(self._hold, 500),
            )
        if kind == ActionType.DELAY:
            return Action(type=kind, delay_ms=self._int(self._delay, 100))
        if kind in (ActionType.ELSE, ActionType.ENDIF):
            return Action(type=kind)
        if kind in (ActionType.FIND_TEXT, ActionType.WAIT_TEXT, ActionType.IF_TEXT):
            query = self._query.get().strip()
            if not query:
                self._on_status("Enter text query first")
                return None
            return Action(
                type=kind,
                query=query,
                button=MouseButton(BUTTON_LABELS[self._button.get()]),
                timeout_ms=self._int(self._timeout, 5000),
                on_fail=OnFail(ON_FAIL_LABELS[self._on_fail.get()]),
                **self._capture_fields(),
            )
        if kind in (ActionType.FIND_IMAGE, ActionType.WAIT_IMAGE, ActionType.IF_IMAGE):
            image_path = self._image.get().strip()
            if not image_path:
                self._on_status("Enter image path or Browse…")
                return None
            return Action(
                type=kind,
                image_path=image_path,
                button=MouseButton(BUTTON_LABELS[self._button.get()]),
                threshold=self._float(self._threshold, 0.85),
                timeout_ms=self._int(self._timeout, 5000),
                on_fail=OnFail(ON_FAIL_LABELS[self._on_fail.get()]),
                **self._capture_fields(),
            )
        self._on_status(f"Unsupported type: {kind.value}")
        return None

    def _add(self) -> None:
        if self._preset is None:
            return
        action = self._build_action_from_form()
        if action is None:
            return
        self.append_action(action)
        self._on_status(f"Added: {action.summary()}")

    def _update(self) -> None:
        """Replace the selected action with the form values."""
        if self._preset is None or self._selected_index is None:
            self._on_status("Select a step in the list first")
            return
        i = self._selected_index
        if i < 0 or i >= len(self._preset.actions):
            self._on_status("Select a step in the list first")
            return
        old = self._preset.actions[i]
        action = self._build_action_from_form()
        if action is None:
            return
        action.id = old.id
        # Keep double-click count when still a plain click.
        if (
            action.type == ActionType.MOUSE_CLICK
            and action.click_phase == ClickPhase.CLICK
            and old.type == ActionType.MOUSE_CLICK
            and old.click_phase == ClickPhase.CLICK
        ):
            action.click_count = old.click_count
        self._preset.actions[i] = action
        self._rebuild_row_at(i, action)
        self._selected_index = i
        self._refresh_selection_styles()
        self._load_action_into_form(action)
        self._on_changed()
        self._on_status(f"Updated step {i + 1}: {action.summary()}")

    def _rebuild_row_at(self, index: int, action: Action) -> None:
        """Replace one list row in place (avoids full list rebuild on Save)."""
        old = self._row_widgets.pop(index)
        self._row_labels.pop(index)
        self._row_tips.pop(index)
        self._row_info.pop(index)
        old.destroy()
        # Build at end then move into place and repack.
        self._append_row(len(self._row_widgets), action)
        row = self._row_widgets.pop()
        label = self._row_labels.pop()
        tip = self._row_tips.pop()
        info = self._row_info.pop()
        self._row_widgets.insert(index, row)
        self._row_labels.insert(index, label)
        self._row_tips.insert(index, tip)
        self._row_info.insert(index, info)
        self._repack_rows()

    def _sync_hold_mode(self) -> None:
        """For hold type, prefer key OR mouse fields to avoid mixed input."""
        if self._selected_type() != ActionType.HOLD:
            return
        self._sync_form_visibility()

    def _sync_form_visibility(self) -> None:
        """Show only fields needed for the selected action type."""
        kind = self._selected_type()
        self._hint.configure(text=TYPE_HINTS.get(kind, ""))
        visible: set[str] = set()
        if kind == ActionType.MOUSE_CLICK:
            visible = {"xy", "button", "phase"}
            self._phase.configure(values=list(PHASE_CLICK.keys()))
            if self._phase.get() not in PHASE_CLICK:
                self._phase.set("Click")
        elif kind == ActionType.MOUSE_MOVE:
            visible = {"xy"}
        elif kind == ActionType.MOUSE_DRAG:
            visible = {"xy", "end_xy", "button", "hold"}
        elif kind == ActionType.KEY:
            visible = {"key", "phase"}
            self._phase.configure(values=list(PHASE_KEY.keys()))
            if self._phase.get() not in PHASE_KEY:
                self._phase.set("Tap")
        elif kind == ActionType.HOTKEY:
            visible = {"hotkeys"}
        elif kind == ActionType.HOLD:
            if self._key.get().strip():
                visible = {"key", "hold"}
            else:
                visible = {"key", "button", "xy", "hold"}
        elif kind == ActionType.DELAY:
            visible = {"delay"}
        elif kind == ActionType.FIND_TEXT:
            visible = {"query", "button", "timeout", "on_fail", "capture"}
        elif kind == ActionType.FIND_IMAGE:
            visible = {"image", "button", "threshold", "timeout", "on_fail", "capture"}
        elif kind == ActionType.WAIT_TEXT:
            visible = {"query", "timeout", "on_fail", "capture"}
        elif kind == ActionType.WAIT_IMAGE:
            visible = {"image", "threshold", "timeout", "on_fail", "capture"}
        elif kind == ActionType.IF_TEXT:
            visible = {"query", "timeout", "capture"}
        elif kind == ActionType.IF_IMAGE:
            visible = {"image", "threshold", "timeout", "capture"}
        elif kind in (ActionType.ELSE, ActionType.ENDIF):
            visible = set()

        if kind in VISION_TYPES:
            values = ["Preset monitor"] + [f"Monitor {m.index}" for m in list_monitors()]
            current = self._cap_mon.get()
            self._cap_mon.configure(values=values)
            self._cap_mon.set(current if current in values else values[0])

        for key, widgets in self._field_rows.items():
            for widget in widgets:
                if key in visible:
                    widget.grid()
                else:
                    widget.grid_remove()
