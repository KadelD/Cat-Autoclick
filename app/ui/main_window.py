"""Main application window wiring presets, editor, player, and recorder."""

from __future__ import annotations

import customtkinter as ctk
from pynput import keyboard

from app.core.models import Preset
from app.core.monitors import list_monitors
from app.core.player import MacroPlayer
from app.core.recorder import MacroRecorder
from app.core.store import PresetStore
from app.ui import theme as T
from app.ui.action_editor import ActionEditor
from app.ui.preset_panel import PresetPanel
from app.ui.theme import apply_app_theme


class MainWindow(ctk.CTk):
    """Cat Autoclick primary UI."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Cat Autoclick")
        self.geometry("1180x760")
        self.minsize(980, 640)
        apply_app_theme()
        self.configure(fg_color=T.BG)

        self.store = PresetStore()
        self.store.ensure_default()
        self._presets = self.store.list_presets()
        self._current: Preset | None = self._presets[0] if self._presets else None
        self._dirty_ids: set[str] = set()
        self._deleted_ids: set[str] = set()

        self.player = MacroPlayer(on_status=self._status_from_thread)
        self.recorder = MacroRecorder(
            on_action=self._action_from_thread,
            on_status=self._status_from_thread,
        )
        self._hotkey_listener: keyboard.GlobalHotKeys | None = None

        self._build()
        self._load_monitors()
        self._bind_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self._current:
            self.preset_panel.set_presets(self._presets, self._current.id)
            self.editor.set_preset(self._current)
            self._sync_controls_from_preset()

    def _menu(self, master: ctk.CTkBaseClass, values: list[str], command=None) -> ctk.CTkOptionMenu:
        """Create a themed option menu."""
        return ctk.CTkOptionMenu(
            master,
            values=values,
            command=command,
            fg_color=T.NAVY,
            button_color=T.PURPLE_DIM,
            button_hover_color=T.PURPLE,
            dropdown_fg_color=T.PANEL,
            dropdown_hover_color=T.NAVY,
            text_color=T.WHITE,
        )

    def _entry(self, master: ctk.CTkBaseClass, width: int = 70) -> ctk.CTkEntry:
        """Create a themed entry field."""
        return ctk.CTkEntry(
            master,
            width=width,
            fg_color=T.INPUT,
            border_color=T.BORDER,
            text_color=T.WHITE,
        )

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.preset_panel = PresetPanel(
            self,
            on_select=self._on_select_preset,
            on_changed=self._on_presets_mutated,
            width=250,
        )
        self.preset_panel.grid(row=0, column=0, sticky="nsw", padx=(14, 8), pady=14)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 14), pady=14)
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(center, fg_color=T.PANEL, corner_radius=14)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.grid_columnconfigure(3, weight=1)

        brand = ctk.CTkLabel(
            top,
            text="Cat Autoclick",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=T.WHITE,
        )
        brand.grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 2))
        subtitle = ctk.CTkLabel(
            top,
            text="Record or build macros · keyboard, mouse, chords & holds",
            text_color=T.MUTED,
        )
        subtitle.grid(row=1, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 8))

        ctk.CTkLabel(top, text="Monitor", text_color=T.MUTED).grid(
            row=2, column=0, sticky="w", padx=14, pady=6
        )
        self.monitor_menu = self._menu(top, ["0"], command=self._on_monitor_change)
        self.monitor_menu.grid(row=2, column=1, sticky="w", padx=4, pady=6)

        ctk.CTkLabel(top, text="Loops (0=∞)", text_color=T.MUTED).grid(
            row=2, column=2, sticky="w", padx=12, pady=6
        )
        self.loop_entry = self._entry(top)
        self.loop_entry.insert(0, "1")
        self.loop_entry.grid(row=2, column=3, sticky="w", padx=4, pady=6)
        self.loop_entry.bind("<FocusOut>", lambda _e: self._apply_loop())

        ctk.CTkLabel(top, text="Jitter ms", text_color=T.MUTED).grid(
            row=3, column=0, sticky="w", padx=14, pady=(6, 12)
        )
        self.jitter_entry = self._entry(top)
        self.jitter_entry.insert(0, "10")
        self.jitter_entry.grid(row=3, column=1, sticky="w", padx=4, pady=(6, 12))
        self.jitter_entry.bind("<FocusOut>", lambda _e: self._apply_jitter())

        self.status_label = ctk.CTkLabel(
            top,
            text="Ready",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=T.CYAN,
        )
        self.status_label.grid(row=3, column=2, columnspan=2, sticky="w", padx=12, pady=(6, 12))

        self.editor = ActionEditor(
            center,
            on_changed=self._mark_dirty,
            on_status=self.set_status,
        )
        self.editor.grid(row=1, column=0, sticky="nsew")

        bar = ctk.CTkFrame(center, fg_color=T.PANEL, corner_radius=14)
        bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.btn_record = ctk.CTkButton(
            bar,
            text="Record (F9)",
            width=120,
            height=36,
            fg_color=T.RECORD,
            hover_color=T.RECORD_HOVER,
            text_color=T.WHITE,
            command=self.toggle_record,
        )
        self.btn_record.pack(side="left", padx=(12, 6), pady=12)
        self.btn_play = ctk.CTkButton(
            bar,
            text="Play (F8)",
            width=110,
            height=36,
            fg_color=T.CYAN_DIM,
            hover_color=T.CYAN,
            text_color=T.BG,
            command=self.toggle_play,
        )
        self.btn_play.pack(side="left", padx=4, pady=12)
        self.btn_pause = ctk.CTkButton(
            bar,
            text="Pause",
            width=90,
            height=36,
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self.player.toggle_pause,
        )
        self.btn_pause.pack(side="left", padx=4, pady=12)
        self.btn_stop = ctk.CTkButton(
            bar,
            text="Stop (F10)",
            width=100,
            height=36,
            fg_color=T.STOP,
            hover_color=T.STOP_HOVER,
            text_color=T.WHITE,
            command=self.stop_all,
        )
        self.btn_stop.pack(side="left", padx=4, pady=12)
        ctk.CTkButton(
            bar,
            text="Save",
            width=90,
            height=36,
            fg_color=T.PURPLE,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self.save_all,
        ).pack(side="right", padx=12, pady=12)

        hint = ctk.CTkLabel(
            center,
            text="Hotkeys: F8 play/stop · F9 record/stop · F10 stop all  ·  Coordinates are relative to the selected monitor",
            text_color=T.MUTED,
            font=ctk.CTkFont(size=11),
        )
        hint.grid(row=3, column=0, sticky="w", pady=(8, 0), padx=4)

    def _load_monitors(self) -> None:
        monitors = list_monitors()
        labels = [m.label for m in monitors]
        self._monitor_labels = labels
        self.monitor_menu.configure(values=labels)
        idx = self._current.monitor_index if self._current else 0
        if 0 <= idx < len(labels):
            self.monitor_menu.set(labels[idx])
        else:
            self.monitor_menu.set(labels[0])

    def _monitor_index_from_menu(self) -> int:
        value = self.monitor_menu.get()
        try:
            return int(value.split(":", 1)[0])
        except ValueError:
            return 0

    def _on_monitor_change(self, _value: str) -> None:
        if self._current is None:
            return
        self._current.monitor_index = self._monitor_index_from_menu()
        self._mark_dirty()

    def _apply_loop(self) -> None:
        if self._current is None:
            return
        try:
            self._current.loop_count = int(self.loop_entry.get().strip())
        except ValueError:
            self._current.loop_count = 1
            self.loop_entry.delete(0, "end")
            self.loop_entry.insert(0, "1")
        self._mark_dirty()

    def _apply_jitter(self) -> None:
        if self._current is None:
            return
        try:
            self._current.jitter_ms = max(0, int(self.jitter_entry.get().strip()))
        except ValueError:
            self._current.jitter_ms = 10
            self.jitter_entry.delete(0, "end")
            self.jitter_entry.insert(0, "10")
        self._mark_dirty()

    def _sync_controls_from_preset(self) -> None:
        if self._current is None:
            return
        self.loop_entry.delete(0, "end")
        self.loop_entry.insert(0, str(self._current.loop_count))
        self.jitter_entry.delete(0, "end")
        self.jitter_entry.insert(0, str(self._current.jitter_ms))
        labels = getattr(self, "_monitor_labels", None) or self.monitor_menu.cget("values")
        idx = self._current.monitor_index
        if labels and 0 <= idx < len(labels):
            self.monitor_menu.set(labels[idx])

    def _on_select_preset(self, preset: Preset | None) -> None:
        self._apply_loop()
        self._apply_jitter()
        self._current = preset
        self.editor.set_preset(preset)
        self._sync_controls_from_preset()
        self.set_status("Ready" if preset else "No preset")

    def _on_presets_mutated(self) -> None:
        self._presets = self.preset_panel.presets
        disk_ids = {p.id for p in self.store.list_presets()}
        live_ids = {p.id for p in self._presets}
        self._deleted_ids |= disk_ids - live_ids
        for p in self._presets:
            self._dirty_ids.add(p.id)
        self._current = self.preset_panel.selected()
        self.editor.set_preset(self._current)
        self._sync_controls_from_preset()

    def _mark_dirty(self) -> None:
        if self._current is not None:
            self._dirty_ids.add(self._current.id)

    def save_all(self) -> None:
        self._apply_loop()
        self._apply_jitter()
        if self._current is not None:
            self._current.monitor_index = self._monitor_index_from_menu()
        for preset_id in list(self._deleted_ids):
            self.store.delete(preset_id)
        self._deleted_ids.clear()
        for preset in self._presets:
            self.store.save(preset)
        self._dirty_ids.clear()
        selected = self._current.id if self._current else None
        self._presets = self.store.list_presets()
        self.preset_panel.set_presets(self._presets, selected)
        self._current = self.preset_panel.selected()
        self.editor.set_preset(self._current)
        self.set_status("Saved")

    def set_status(self, message: str) -> None:
        self.status_label.configure(text=message)

    def _status_from_thread(self, message: str) -> None:
        def _apply() -> None:
            self.set_status(message)
            if message in ("Finished", "Stopped") or message.startswith("Hotkeys"):
                self._set_play_idle()

        self.after(0, _apply)

    def _action_from_thread(self, action) -> None:
        self.after(0, lambda: self.editor.append_action(action))

    def toggle_record(self) -> None:
        if self.recorder.is_recording:
            self.recorder.stop()
            self.btn_record.configure(text="Record (F9)")
            return
        if self.player.is_running:
            self.player.stop()
        if self._current is None:
            self.set_status("Create a preset first")
            return
        self._apply_loop()
        ignore = [
            self._current.play_hotkey,
            self._current.record_hotkey,
            self._current.stop_hotkey,
        ]
        self.recorder.set_ignore_hotkeys(ignore)
        self.recorder.start(self._current.monitor_index)
        self.btn_record.configure(text="Stop Rec (F9)")

    def toggle_play(self) -> None:
        if self.player.is_running:
            self.player.stop()
            self._set_play_idle()
            return
        if self.recorder.is_recording:
            self.recorder.stop()
            self.btn_record.configure(text="Record (F9)")
        if self._current is None:
            self.set_status("No preset selected")
            return
        self._apply_loop()
        self._apply_jitter()
        self._current.monitor_index = self._monitor_index_from_menu()
        self.player.play(self._current)
        self.btn_play.configure(
            text="Stop (F8)",
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
        )

    def _set_play_idle(self) -> None:
        """Reset Play button to the idle cyan style."""
        self.btn_play.configure(
            text="Play (F8)",
            fg_color=T.CYAN_DIM,
            hover_color=T.CYAN,
            text_color=T.BG,
        )

    def stop_all(self) -> None:
        if self.recorder.is_recording:
            self.recorder.stop()
            self.btn_record.configure(text="Record (F9)")
        if self.player.is_running:
            self.player.stop()
        self._set_play_idle()
        self.set_status("Stopped")

    def _bind_hotkeys(self) -> None:
        mapping = {
            "<f8>": lambda: self.after(0, self.toggle_play),
            "<f9>": lambda: self.after(0, self.toggle_record),
            "<f10>": lambda: self.after(0, self.stop_all),
        }
        try:
            self._hotkey_listener = keyboard.GlobalHotKeys(mapping)
            self._hotkey_listener.start()
        except Exception as exc:
            self.set_status(f"Hotkeys unavailable: {exc}")

    def _on_close(self) -> None:
        self.stop_all()
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
        self.destroy()


def run_app() -> None:
    """Launch the Cat Autoclick UI."""
    app = MainWindow()
    app.mainloop()
