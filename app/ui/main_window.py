"""Cat Automation Studio — PySide6 main window."""



from __future__ import annotations



import sys



from PySide6.QtCore import Qt

from PySide6.QtGui import QCloseEvent, QKeySequence, QAction

from PySide6.QtWidgets import (

    QApplication,

    QInputDialog,

    QMainWindow,

    QMessageBox,

    QSplitter,

    QStatusBar,

    QWidget,

)



from app import __version__

from app.application.app_controller import AppController

from app.application.app_state import AppState

from app.application.workflow_ops import if_block_span

from app.core.models import ActionType

from app.core.settings import load_settings

from app.ui.layout.inspector_panel import InspectorPanel

from app.ui.layout.sidebar import PresetSidebar

from app.ui.layout.top_bar import TopBar

from app.ui.layout.workflow_panel import WorkflowPanel

from app.ui.dialogs.ocr_capture_dialog import OcrCaptureDialog

from app.ui.dialogs.settings_dialog import SettingsDialog

from app.ui.overlays.record_hud import RecordHud

from app.ui.overlays.region_picker import RegionPickerOverlay

from app.ui.styles.stylesheet import build_stylesheet





class StudioMainWindow(QMainWindow):

    """Three-column automation IDE shell."""



    def __init__(self, controller: AppController) -> None:

        super().__init__()

        self._controller = controller

        self._record_hud: RecordHud | None = None

        self._region_picker: RegionPickerOverlay | None = None

        self._ocr_busy = False

        self.setWindowTitle(f"Cat Automation Studio — {__version__}")

        self.resize(1440, 900)

        self.setMinimumSize(1100, 700)



        central = QWidget()

        self.setCentralWidget(central)

        from PySide6.QtWidgets import QVBoxLayout



        root = QVBoxLayout(central)

        root.setContentsMargins(0, 0, 0, 0)

        root.setSpacing(0)



        self.top_bar = TopBar()

        root.addWidget(self.top_bar)



        split = QSplitter(Qt.Horizontal)

        self.sidebar = PresetSidebar()

        self.workflow = WorkflowPanel(controller.macros)

        self.inspector = InspectorPanel()

        split.addWidget(self.sidebar)

        split.addWidget(self.workflow)

        split.addWidget(self.inspector)

        split.setStretchFactor(0, 0)

        split.setStretchFactor(1, 1)

        split.setStretchFactor(2, 0)

        split.setSizes([260, 820, 320])

        root.addWidget(split, stretch=1)



        status = QStatusBar()

        self.setStatusBar(status)

        status.showMessage("Ready")



        self._wire()

        self._refresh_presets()

        if controller.macros.current:

            self.workflow.load_preset()

        controller.initialize()

        controller.state_changed.connect(self.top_bar.set_app_state)

        controller.state_changed.connect(self._on_state)

        controller.status_message.connect(status.showMessage)

        controller.error_message.connect(self._show_error)

        controller.macros.presets_changed.connect(self._refresh_presets)

        controller.macros.preset_selected.connect(lambda _p: self.workflow.load_preset())

        controller.macros.macro_changed.connect(lambda _p: self.workflow.load_preset())

        controller.macros.dirty_changed.connect(self._update_title)

        controller.macros.selection_changed.connect(self._on_selection_changed)

        controller.recording.action_captured.connect(lambda _a: self.workflow.load_preset())

        controller.playback.execution_step_changed.connect(self.workflow.set_execution_step)

        controller.macros.step_updated.connect(self._refresh_inspector)

        controller.recording.started.connect(self._show_record_hud)

        controller.recording.stopped.connect(self._hide_record_hud)

        controller.recording.status.connect(self._record_hud_status)

        controller.ocr_full_requested.connect(lambda: self._begin_ocr_capture(full=True))

        controller.ocr_area_requested.connect(lambda: self._begin_ocr_capture(full=False))



        self.top_bar.set_app_state(AppState.IDLE)

        settings = load_settings()

        if settings.start_minimized:

            self.showMinimized()

        else:

            self.show()



    def _wire(self) -> None:

        c = self._controller

        self.top_bar.record_clicked.connect(c.toggle_record)

        self.top_bar.run_clicked.connect(c.toggle_play)

        self.top_bar.pause_clicked.connect(c.playback.toggle_pause)

        self.top_bar.stop_clicked.connect(c.stop_all)

        self.top_bar.macro_changed.connect(c.macros.select)

        self.top_bar.macro_changed.connect(lambda _id: self.workflow.load_preset())



        self.sidebar.preset_selected.connect(c.macros.select)

        self.sidebar.preset_selected.connect(lambda _id: self.workflow.load_preset())

        self.sidebar.new_macro_requested.connect(self._new_macro)



        self.workflow.save_requested.connect(c.macros.save_all)

        self.workflow.step_selected.connect(self._on_step_selected)

        self.workflow.record_requested.connect(c.toggle_record)

        self.inspector.delete_requested.connect(self._delete_step)

        self.inspector.save_action.connect(self._save_step)

        self.inspector.pick_region.connect(self._pick_region)

        self.top_bar.settings_clicked.connect(self._open_settings)



        save_action = QAction("Save", self)

        save_action.setShortcut(QKeySequence.Save)

        save_action.triggered.connect(c.macros.save_all)

        self.addAction(save_action)



    def _refresh_presets(self) -> None:

        presets = self._controller.macros.presets

        names = [p.name for p in presets]

        ids = [p.id for p in presets]

        cur = self._controller.macros.current

        self.sidebar.set_presets(names, ids, cur.id if cur else None)

        self.top_bar.set_macros(names, cur.id if cur else None, ids)

        self._update_title(self._controller.macros.is_dirty)



    def _update_title(self, dirty: bool) -> None:

        base = f"Cat Automation Studio — {__version__}"

        preset = self._controller.macros.current

        if preset:

            base = f"{base} — {preset.name}"

        if dirty:

            base += " *"

        self.setWindowTitle(base)



    def _on_state(self, state: AppState) -> None:
        settings = self._controller.settings
        if state == AppState.RECORDING and settings.hide_on_record:
            self.hide()
            return
        if state == AppState.PLAYING and settings.hide_on_play:
            self.hide()
            return
        # Show again when idle, paused, or when hide_* is off for current mode.
        if state in (AppState.IDLE, AppState.PAUSED) or (
            state == AppState.PLAYING and not settings.hide_on_play
        ):
            if not self.isVisible():
                self.show()
                self.raise_()
                self.activateWindow()



    def _new_macro(self) -> None:

        name, ok = QInputDialog.getText(self, "New Macro", "Name:")

        if ok and name.strip():

            self._controller.macros.create_preset(name.strip())

            self.workflow.load_preset()



    def _on_step_selected(self, index: int) -> None:

        preset = self._controller.macros.current

        if preset and 0 <= index < len(preset.actions):

            self.inspector.show_action(index, preset.actions[index])



    def _on_selection_changed(self, index: object) -> None:

        if index is None:

            self.inspector.clear()



    def _save_step(self, index: int, action) -> None:
        self._controller.macros.update_step(index, action)

    def _refresh_inspector(self, index: int) -> None:
        preset = self._controller.macros.current
        if preset and self._controller.macros.selected_step_index == index:
            if 0 <= index < len(preset.actions):
                self.inspector.show_action(index, preset.actions[index])

    def _show_record_hud(self) -> None:
        preset = self._controller.macros.current
        mon = preset.monitor_index if preset else 0
        self._hide_record_hud()
        self._record_hud = RecordHud(mon, self._controller.settings)
        self._record_hud.show_hud()

    def _hide_record_hud(self) -> None:
        if self._record_hud is not None:
            self._record_hud.close()
            self._record_hud = None

    def _record_hud_status(self, message: str) -> None:
        if self._record_hud is not None:
            self._record_hud.set_status(message)

    def _open_settings(self) -> None:
        SettingsDialog.open_settings(
            self._controller.settings,
            self._controller.apply_settings,
            self,
        )

    def _close_region_picker(self) -> None:
        """Destroy any active region overlay so it cannot trap the desktop."""
        picker = self._region_picker
        self._region_picker = None
        if picker is not None:
            try:
                picker.close()
            except Exception:
                pass

    def _pick_region(self, _step_index: int) -> None:
        """Open region picker for inspector; keep a strong reference until closed."""
        preset = self._controller.macros.current
        if preset is None:
            return
        self._close_region_picker()
        picker = RegionPickerOverlay(preset.monitor_index)
        self._region_picker = picker

        def _done(x: int, y: int, w: int, h: int) -> None:
            self.inspector.apply_region(x, y, w, h)
            self._region_picker = None

        def _cancel() -> None:
            self._region_picker = None

        picker.region_selected.connect(_done)
        picker.cancelled.connect(_cancel)
        picker.destroyed.connect(lambda *_: setattr(self, "_region_picker", None))
        picker.show_picker()

    def _begin_ocr_capture(self, *, full: bool) -> None:
        """Pause recording and add an OCR step (hotkey while recording)."""
        c = self._controller
        if not c.recording.is_recording or self._ocr_busy or c.macros.current is None:
            return
        self._ocr_busy = True
        c.recording.pause()
        self._record_hud_status("OCR setup…")
        mon = c.macros.current.monitor_index
        if full:
            self._open_ocr_dialog(mon, 0, 0, 0, 0)
            return

        self._close_region_picker()
        picker = RegionPickerOverlay(mon)
        self._region_picker = picker

        def _done(x: int, y: int, w: int, h: int) -> None:
            self._region_picker = None
            self._open_ocr_dialog(mon, x, y, w, h)

        def _cancel() -> None:
            self._region_picker = None
            self._finish_ocr_flow(resume=True)
            self._record_hud_status("Recording…")

        picker.region_selected.connect(_done)
        picker.cancelled.connect(_cancel)
        picker.destroyed.connect(lambda *_: setattr(self, "_region_picker", None))
        picker.show_picker()

    def _open_ocr_dialog(
        self, monitor_index: int, rx: int, ry: int, rw: int, rh: int
    ) -> None:
        """Show OCR settings; recorder stays paused until dialog closes."""

        def _ok(action) -> None:
            self._controller.macros.append_action(action)
            self.workflow.load_preset()
            self.statusBar().showMessage(f"Added OCR: {action.summary()}")

        OcrCaptureDialog.run(
            monitor_index=monitor_index,
            region_x=rx,
            region_y=ry,
            region_w=rw,
            region_h=rh,
            on_ok=_ok,
            parent=self,
        )
        self._finish_ocr_flow(resume=True)
        self._record_hud_status("Recording…")

    def _finish_ocr_flow(self, resume: bool) -> None:
        self._ocr_busy = False
        if resume and self._controller.recording.is_recording:
            self._controller.recording.resume()

    def _delete_step(self, index: int) -> None:

        preset = self._controller.macros.current

        if preset is None or not (0 <= index < len(preset.actions)):

            return

        actions = preset.actions

        if actions[index].type in (ActionType.IF_TEXT, ActionType.IF_IMAGE):

            span = if_block_span(actions, index)

            count = span[1] - span[0] + 1

            box = QMessageBox(self)

            box.setWindowTitle("Delete condition")

            box.setText(f"Delete this If block and all {count} steps inside it?")

            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

            if box.exec() != QMessageBox.Yes:

                return

        self._controller.macros.delete_step(index)

        self.inspector.clear()



    def _show_error(self, message: str) -> None:

        QMessageBox.warning(self, "Cat Automation Studio", message)



    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._close_region_picker()
        self._hide_record_hud()

        if self._controller.macros.is_dirty:

            box = QMessageBox(self)

            box.setWindowTitle("Unsaved changes")

            box.setText("You have unsaved changes.")

            save = box.addButton("Save", QMessageBox.AcceptRole)

            discard = box.addButton("Don't Save", QMessageBox.DestructiveRole)

            cancel = box.addButton("Cancel", QMessageBox.RejectRole)

            box.exec()

            clicked = box.clickedButton()

            if clicked == cancel:

                event.ignore()

                return

            if clicked == save:

                self._controller.macros.save_all()

        self._controller.shutdown()

        event.accept()





def run_app() -> None:

    """Launch Cat Automation Studio (PySide6)."""

    app = QApplication.instance() or QApplication(sys.argv)

    app.setStyle("Fusion")

    app.setStyleSheet(build_stylesheet())

    controller = AppController()

    window = StudioMainWindow(controller)

    sys.exit(app.exec())


