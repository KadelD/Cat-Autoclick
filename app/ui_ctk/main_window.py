"""Main application window wiring presets, editor, player, and recorder."""

from __future__ import annotations

import customtkinter as ctk
from pynput import keyboard

from app import __version__
from app.core.models import Action, Preset
from app.core.monitors import list_monitors
from app.core.player import MacroPlayer
from app.core.recorder import MacroRecorder
from app.core.settings import AppSettings, load_settings
from app.core.store import PresetStore
from app.ui_ctk import theme as T
from app.ui_ctk.action_editor import ActionEditor
from app.ui_ctk.ocr_capture_dialog import OcrCaptureDialog
from app.ui_ctk.preset_panel import PresetPanel
from app.ui_ctk.record_hud import RecordHud
from app.ui_ctk.region_picker import pick_region
from app.ui_ctk.settings_dialog import SettingsDialog
from app.ui_ctk.theme import apply_app_theme
from app.ui_ctk.tooltip import HoverTip


class MainWindow(ctk.CTk):
    """Cat Autoclick primary UI."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"Cat Autoclick {__version__}")
        self.geometry("1180x760")
        self.minsize(980, 640)
        apply_app_theme()
        self.configure(fg_color=T.BG)

        self._settings = load_settings()
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
        self._record_hud: RecordHud | None = None
        self._ocr_busy = False
        self._pending_record_actions: list[Action] = []
        self._record_flush_job: str | None = None
        self._settings_dialog: SettingsDialog | None = None
        # Hidden host so OCR dialogs/pickers still show while the main window is withdrawn.
        self._overlay_host = ctk.CTkToplevel(self)
        self._overlay_host.withdraw()

        self._build()
        self._load_monitors()
        self._apply_settings(self._settings, persist_ui_only=True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self._current:
            self.preset_panel.set_presets(self._presets, self._current.id)
            self.editor.set_preset(self._current)
            self._sync_controls_from_preset()

        if self._settings.start_minimized:
            self.after(80, self.iconify)

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
            text="Record",
            width=140,
            height=36,
            fg_color=T.RECORD,
            hover_color=T.RECORD_HOVER,
            text_color=T.WHITE,
            command=self.toggle_record,
        )
        self.btn_record.pack(side="left", padx=(12, 6), pady=12)
        self._tip_record = HoverTip(self.btn_record, "")
        self.btn_play = ctk.CTkButton(
            bar,
            text="Play",
            width=130,
            height=36,
            fg_color=T.CYAN_DIM,
            hover_color=T.CYAN,
            text_color=T.BG,
            command=self.toggle_play,
        )
        self.btn_play.pack(side="left", padx=4, pady=12)
        self._tip_play = HoverTip(self.btn_play, "")
        self.btn_pause = ctk.CTkButton(
            bar,
            text="Pause",
            width=90,
            height=36,
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self._toggle_pause,
            state="disabled",
        )
        self.btn_pause.pack(side="left", padx=4, pady=12)
        self.btn_stop = ctk.CTkButton(
            bar,
            text="Stop",
            width=130,
            height=36,
            fg_color=T.STOP,
            hover_color=T.STOP_HOVER,
            text_color=T.WHITE,
            command=self.stop_all,
        )
        self.btn_stop.pack(side="left", padx=4, pady=12)
        self._tip_stop = HoverTip(self.btn_stop, "")
        ctk.CTkButton(
            bar,
            text="Save",
            width=90,
            height=36,
            fg_color=T.PURPLE,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self.save_all,
        ).pack(side="right", padx=(6, 12), pady=12)
        ctk.CTkButton(
            bar,
            text="Settings",
            width=90,
            height=36,
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
            command=self._open_settings,
        ).pack(side="right", padx=(12, 0), pady=12)

        self.hint_label = ctk.CTkLabel(
            center,
            text="",
            text_color=T.MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.hint_label.grid(row=3, column=0, sticky="w", pady=(8, 0), padx=4)

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
        if self._record_hud is not None:
            self._record_hud.set_status(message)

    def _status_from_thread(self, message: str) -> None:
        def _apply() -> None:
            self.set_status(message)
            if message in ("Finished", "Stopped") or message.startswith("Hotkeys"):
                self._set_play_idle()

        self.after(0, _apply)

    def _action_from_thread(self, action: Action) -> None:
        """Batch recorded actions onto the UI thread (~60fps) to avoid scroll lag."""
        self._pending_record_actions.append(action)
        if self._record_flush_job is None:
            self._record_flush_job = self.after(16, self._flush_recorded_actions)

    def _flush_recorded_actions(self) -> None:
        """Append queued recorder actions in one UI tick."""
        self._record_flush_job = None
        batch = self._pending_record_actions
        self._pending_record_actions = []
        for action in batch:
            self.editor.append_action(action)

    def _show_record_ui(self) -> None:
        """Show floating record HUD; optionally hide the main window."""
        mon = self._current.monitor_index if self._current else 0
        self._destroy_record_hud()
        self._record_hud = RecordHud(self, mon, settings=self._settings)
        if self._settings.hide_on_record:
            self.withdraw()

    def _restore_main_ui(self) -> None:
        """Bring the main window back after recording ends."""
        self._destroy_record_hud()
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _destroy_record_hud(self) -> None:
        if self._record_hud is not None:
            self._record_hud.destroy()
            self._record_hud = None

    def _end_record_session(self) -> None:
        """Stop recorder listeners and restore the main window."""
        if self.recorder.is_recording:
            self.recorder.stop()
        self._refresh_button_labels(recording=False)
        self._ocr_busy = False
        self._restore_main_ui()

    def toggle_record(self) -> None:
        if self.recorder.is_recording:
            self._end_record_session()
            return
        if self.player.is_running:
            self.player.stop()
        if self._current is None:
            self.set_status("Create a preset first")
            return
        self._apply_loop()
        # Chord hotkeys are swallowed by the recorder; do not ignore plain keys.
        self.recorder.set_ignore_hotkeys([])
        self.recorder.start(self._current.monitor_index)
        self._refresh_button_labels(recording=True)
        self._show_record_ui()
        self.set_status("Recording…")

    def toggle_play(self) -> None:
        if self.player.is_running:
            self.player.stop()
            self._set_play_idle()
            return
        if self.recorder.is_recording:
            self._end_record_session()
        if self._current is None:
            self.set_status("No preset selected")
            return
        self._apply_loop()
        self._apply_jitter()
        self._current.monitor_index = self._monitor_index_from_menu()
        self.player.play(self._current)
        play_hk = self._settings.display_hotkey("play")
        self.btn_play.configure(
            text=f"Stop ({play_hk})",
            fg_color=T.NAVY,
            hover_color=T.PURPLE_DIM,
            text_color=T.WHITE,
        )
        self._sync_pause_button()
        if self._settings.hide_on_play:
            self.withdraw()

    def _toggle_pause(self) -> None:
        """Pause/resume playback; ignored when idle."""
        if not self.player.is_running:
            return
        self.player.toggle_pause()
        self._sync_pause_button()

    def _sync_pause_button(self) -> None:
        """Enable Pause only while playing; flip label when paused."""
        if not self.player.is_running:
            self.btn_pause.configure(text="Pause", state="disabled")
            return
        self.btn_pause.configure(
            text="Resume" if self.player.is_paused else "Pause",
            state="normal",
        )

    def _set_play_idle(self) -> None:
        """Reset Play button to the idle cyan style."""
        play_hk = self._settings.display_hotkey("play")
        self.btn_play.configure(
            text=f"Play ({play_hk})",
            fg_color=T.CYAN_DIM,
            hover_color=T.CYAN,
            text_color=T.BG,
        )
        self._sync_pause_button()
        if self._settings.hide_on_play and not self.recorder.is_recording:
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception:
                pass

    def stop_all(self) -> None:
        if self.recorder.is_recording:
            self._end_record_session()
        if self.player.is_running:
            self.player.stop()
        self._set_play_idle()
        self.set_status("Stopped")

    def _ocr_full(self) -> None:
        """Insert OCR step for the full preset monitor (while recording)."""
        if not self._settings.ocr_enabled:
            self.set_status("OCR is disabled in Settings")
            return
        self._begin_ocr_capture(full=True)

    def _ocr_area(self) -> None:
        """Pick a region then insert an OCR step (while recording)."""
        if not self._settings.ocr_enabled:
            self.set_status("OCR is disabled in Settings")
            return
        self._begin_ocr_capture(full=False)

    def _begin_ocr_capture(self, full: bool) -> None:
        if not self.recorder.is_recording or self._ocr_busy or self._current is None:
            return
        self._ocr_busy = True
        self.recorder.pause()
        mon = self._current.monitor_index
        if self._record_hud is not None:
            self._record_hud.set_status("OCR setup…")

        if full:
            self._open_ocr_dialog(mon, 0, 0, 0, 0)
            return

        def _done(x: int, y: int, w: int, h: int) -> None:
            self._open_ocr_dialog(mon, x, y, w, h)

        def _cancel() -> None:
            self._finish_ocr_flow(resume=True)
            if self._record_hud is not None:
                self._record_hud.set_status("Recording…")

        pick_region(self._overlay_host, mon, on_done=_done, on_cancel=_cancel)

    def _open_ocr_dialog(
        self, monitor_index: int, rx: int, ry: int, rw: int, rh: int
    ) -> None:
        """Show OCR settings; clicks/keys here are ignored by the paused recorder."""

        def _ok(action: Action) -> None:
            self.editor.append_action(action)
            self._mark_dirty()
            self._finish_ocr_flow(resume=True)
            if self._record_hud is not None:
                self._record_hud.set_status("Recording…")
            self.set_status(f"Added OCR: {action.summary()}")

        def _cancel() -> None:
            self._finish_ocr_flow(resume=True)
            if self._record_hud is not None:
                self._record_hud.set_status("Recording…")

        OcrCaptureDialog(
            self._overlay_host,
            monitor_index=monitor_index,
            region_x=rx,
            region_y=ry,
            region_w=rw,
            region_h=rh,
            on_ok=_ok,
            on_cancel=_cancel,
        )

    def _finish_ocr_flow(self, resume: bool) -> None:
        self._ocr_busy = False
        if resume and self.recorder.is_recording:
            self.recorder.resume()

    def _open_settings(self) -> None:
        """Open the app Settings dialog (single instance)."""
        try:
            if self._settings_dialog is not None and self._settings_dialog.winfo_exists():
                self._settings_dialog.lift()
                self._settings_dialog.focus_force()
                return
        except Exception:
            self._settings_dialog = None
        self._settings_dialog = SettingsDialog(
            self,
            self._settings,
            on_apply=self._on_settings_saved,
        )

    def _on_settings_saved(self, settings: AppSettings) -> None:
        """Apply newly saved settings to listeners and UI."""
        self._settings_dialog = None
        self._apply_settings(settings)

    def _apply_settings(self, settings: AppSettings, *, persist_ui_only: bool = False) -> None:
        """Rebuild hotkeys, labels, OCR gates, and recorder swallow list."""
        self._settings = settings
        if not persist_ui_only:
            # Cache already updated by save_settings; keep local reference.
            pass
        self.editor.set_ocr_enabled(settings.ocr_enabled)
        chords = list(settings.hotkey_map().values())
        if not settings.ocr_enabled:
            chords = [
                settings.hotkey_map()["play"],
                settings.hotkey_map()["record"],
                settings.hotkey_map()["stop"],
            ]
        self.recorder.set_app_hotkeys(chords)
        self._refresh_button_labels(recording=self.recorder.is_recording)
        self._bind_hotkeys()
        self.set_status("Settings saved" if not persist_ui_only else "Ready")

    def _refresh_button_labels(self, *, recording: bool) -> None:
        """Update toolbar labels and footer from current hotkeys."""
        s = self._settings
        play_hk = s.display_hotkey("play")
        rec_hk = s.display_hotkey("record")
        stop_hk = s.display_hotkey("stop")
        if recording:
            self.btn_record.configure(text=f"Stop Rec ({rec_hk})")
        else:
            self.btn_record.configure(text=f"Record ({rec_hk})")
        if not self.player.is_running:
            self.btn_play.configure(text=f"Play ({play_hk})")
        else:
            self.btn_play.configure(text=f"Stop ({play_hk})")
        self.btn_stop.configure(text=f"Stop ({stop_hk})")

        ocr_bits = ""
        if s.ocr_enabled:
            ocr_bits = (
                f" · {s.display_hotkey('ocr_full')}/{s.display_hotkey('ocr_area')} OCR while recording"
            )
        self.hint_label.configure(
            text=(
                f"Hotkeys: {play_hk} play · {rec_hk} record · {stop_hk} stop"
                f"{ocr_bits}  ·  Plain keys are recordable"
            )
        )
        hide_note = (
            "Hides this window and shows a floating tip."
            if s.hide_on_record
            else "Keeps this window visible; floating tip still shows."
        )
        tip_ocr = ""
        if s.ocr_enabled:
            tip_ocr = (
                f"\nWhile recording: {s.display_hotkey('ocr_full')} OCR full · "
                f"{s.display_hotkey('ocr_area')} OCR area."
            )
        self._tip_record.set_text(
            f"Start recording ({rec_hk}). {hide_note}{tip_ocr}\n"
            "Plain keys are recorded; app hotkeys use the chords in Settings."
        )
        self._tip_play.set_text(f"Play / stop the selected preset ({play_hk}).")
        self._tip_stop.set_text(f"Stop playback and recording ({stop_hk}).")

    def _bind_hotkeys(self) -> None:
        """Rebuild GlobalHotKeys from current settings."""
        if self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None

        actions = {
            "play": self.toggle_play,
            "record": self.toggle_record,
            "stop": self.stop_all,
            "ocr_full": self._ocr_full,
            "ocr_area": self._ocr_area,
        }
        mapping: dict[str, object] = {}
        for pattern, action_name in self._settings.pynput_hotkeys().items():
            if action_name.startswith("ocr_") and not self._settings.ocr_enabled:
                continue
            handler = actions.get(action_name)
            if handler is None:
                continue
            mapping[pattern] = lambda h=handler: self.after(0, h)
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
