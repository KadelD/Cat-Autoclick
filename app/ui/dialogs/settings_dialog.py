"""Application settings (PySide6)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from pynput import keyboard

from app.core.settings import (
    AppSettings,
    apply_auto_start,
    format_hotkey_display,
    normalize_hotkey,
    read_auto_start_enabled,
    save_settings,
)
from app.ui.styles.tokens import Colors

ApplyCallback = Callable[[AppSettings], None]

_HOTKEY_FIELDS = (
    ("hotkey_play", "Play"),
    ("hotkey_record", "Record"),
    ("hotkey_stop", "Stop"),
    ("hotkey_ocr_full", "OCR full"),
    ("hotkey_ocr_area", "OCR area"),
)


class SettingsDialog(QDialog):
    """Edit hotkeys, window, startup, mouse, and OCR options."""

    def __init__(self, settings: AppSettings, on_apply: ApplyCallback | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(480, 640)
        self._on_apply = on_apply or (lambda _s: None)
        self._settings = AppSettings.from_dict(settings.to_dict())
        self._hotkey_labels: dict[str, QLabel] = {}
        self._capture_field: str | None = None
        self._listener: keyboard.Listener | None = None

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QVBoxLayout(body)

        form.addWidget(self._section("Hotkeys"))
        form.addWidget(QLabel("Click Set, then press a shortcut."))
        for field, title in _HOTKEY_FIELDS:
            form.addLayout(self._hotkey_row(field, title))

        form.addWidget(self._section("Window"))
        self._start_min = QCheckBox("Start minimized")
        self._start_min.setChecked(self._settings.start_minimized)
        form.addWidget(self._start_min)
        self._hide_rec = QCheckBox("Hide main window while recording (HUD stays visible)")
        self._hide_rec.setChecked(self._settings.hide_on_record)
        form.addWidget(self._hide_rec)
        self._hide_play = QCheckBox("Hide main window while playing")
        self._hide_play.setChecked(self._settings.hide_on_play)
        form.addWidget(self._hide_play)

        form.addWidget(self._section("Startup"))
        self._auto_start = QCheckBox("Launch with Windows")
        self._auto_start.setChecked(self._settings.auto_start or read_auto_start_enabled())
        form.addWidget(self._auto_start)

        form.addWidget(self._section("Mouse playback"))
        self._humanize = QCheckBox("Humanize mouse (Bezier path before click/move)")
        self._humanize.setChecked(self._settings.humanize_mouse)
        form.addWidget(self._humanize)
        mouse_form = QFormLayout()
        self._move_ms = QLineEdit(str(self._settings.mouse_move_ms))
        self._curve = QLineEdit(str(self._settings.mouse_curve))
        self._hover_ms = QLineEdit(str(self._settings.mouse_hover_ms))
        mouse_form.addRow("Move ms", self._move_ms)
        mouse_form.addRow("Curve 0–1", self._curve)
        mouse_form.addRow("Hover ms", self._hover_ms)
        form.addLayout(mouse_form)

        form.addWidget(self._section("Vision / OCR"))
        self._ocr = QCheckBox("Enable OCR (EasyOCR Thai + English)")
        self._ocr.setChecked(self._settings.ocr_enabled)
        form.addWidget(self._ocr)

        scroll.setWidget(body)
        root.addWidget(scroll)

        self._error = QLabel("")
        self._error.setStyleSheet(f"color: {Colors.ERROR};")
        root.addWidget(self._error)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)

    def _section(self, title: str) -> QLabel:
        lab = QLabel(title)
        lab.setStyleSheet(f"color: {Colors.ACCENT}; font-weight: 600; font-size: 13px;")
        return lab

    def _hotkey_row(self, field: str, title: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(title))
        val = format_hotkey_display(getattr(self._settings, field))
        label = QLabel(val)
        self._hotkey_labels[field] = label
        row.addWidget(label, stretch=1)
        btn = QPushButton("Set")
        btn.clicked.connect(lambda: self._begin_capture(field))
        row.addWidget(btn)
        return row

    def _begin_capture(self, field: str) -> None:
        """Listen for the next keyboard chord."""
        self._stop_capture()
        self._capture_field = field
        self._hotkey_labels[field].setText("Press keys…")
        held: set[str] = set()

        def on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
            name = _key_name(key)
            if not name:
                return
            held.add(name)
            if name not in ("ctrl", "alt", "shift", "win"):
                mods = [m for m in ("ctrl", "alt", "shift", "win") if m in held]
                chord = normalize_hotkey("+".join(mods + [name]))
                QTimer.singleShot(0, lambda: self._finish_capture(field, chord))

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def _finish_capture(self, field: str, chord: str) -> None:
        self._stop_capture()
        if chord:
            setattr(self._settings, field, chord)
            self._hotkey_labels[field].setText(format_hotkey_display(chord))
        else:
            self._hotkey_labels[field].setText(format_hotkey_display(getattr(self._settings, field)))

    def _stop_capture(self) -> None:
        self._capture_field = None
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _collect(self) -> AppSettings | None:
        try:
            move_ms = int(self._move_ms.text().strip())
            curve = float(self._curve.text().strip())
            hover_ms = int(self._hover_ms.text().strip())
        except ValueError:
            self._error.setText("Mouse fields must be numeric")
            return None
        s = AppSettings(
            hotkey_play=self._settings.hotkey_play,
            hotkey_record=self._settings.hotkey_record,
            hotkey_stop=self._settings.hotkey_stop,
            hotkey_ocr_full=self._settings.hotkey_ocr_full,
            hotkey_ocr_area=self._settings.hotkey_ocr_area,
            start_minimized=self._start_min.isChecked(),
            hide_on_record=self._hide_rec.isChecked(),
            hide_on_play=self._hide_play.isChecked(),
            auto_start=self._auto_start.isChecked(),
            ocr_enabled=self._ocr.isChecked(),
            humanize_mouse=self._humanize.isChecked(),
            mouse_move_ms=max(40, min(3000, move_ms)),
            mouse_curve=max(0.0, min(1.0, curve)),
            mouse_hover_ms=max(0, min(2000, hover_ms)),
        )
        err = s.validate_hotkeys()
        if err:
            self._error.setText(err)
            return None
        return s

    def _save(self) -> None:
        settings = self._collect()
        if settings is None:
            return
        try:
            apply_auto_start(settings.auto_start)
        except Exception as exc:
            self._error.setText(f"Auto-start failed: {exc}")
            return
        save_settings(settings)
        self._stop_capture()
        self._on_apply(settings)
        self.accept()

    def reject(self) -> None:  # noqa: D102
        self._stop_capture()
        super().reject()

    @staticmethod
    def open_settings(settings: AppSettings, on_apply: ApplyCallback, parent=None) -> None:
        """Show modal settings editor."""
        dlg = SettingsDialog(settings, on_apply, parent)
        dlg.exec()


def _key_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    """Normalize pynput key to settings token."""
    if isinstance(key, keyboard.KeyCode):
        if key.char and key.char.isprintable():
            return key.char.lower()
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
