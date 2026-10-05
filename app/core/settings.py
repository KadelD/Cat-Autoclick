"""App-level settings persistence and Windows auto-start helpers."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from app.core.store import project_root

SETTINGS_FILENAME = "settings.json"
_AUTO_START_NAME = "CatAutoclick"


@dataclass
class AppSettings:
    """Process-wide preferences stored next to presets/exe."""

    hotkey_play: str = "ctrl+f8"
    hotkey_record: str = "ctrl+f9"
    hotkey_stop: str = "ctrl+f10"
    hotkey_ocr_full: str = "ctrl+f6"
    hotkey_ocr_area: str = "ctrl+f7"
    start_minimized: bool = False
    hide_on_record: bool = True
    auto_start: bool = False
    ocr_enabled: bool = True
    # Playback: Bezier path + Win32 SendInput (not SetCursorPos) before clicks/moves.
    humanize_mouse: bool = True
    mouse_move_ms: int = 220  # base duration (~scaled by distance)
    mouse_curve: float = 0.35  # 0..1 control-point offset strength
    mouse_hover_ms: int = 60  # dwell at target before click (helps hover gates)

    def hotkey_map(self) -> dict[str, str]:
        """Logical action → normalized hotkey string."""
        return {
            "play": normalize_hotkey(self.hotkey_play),
            "record": normalize_hotkey(self.hotkey_record),
            "stop": normalize_hotkey(self.hotkey_stop),
            "ocr_full": normalize_hotkey(self.hotkey_ocr_full),
            "ocr_area": normalize_hotkey(self.hotkey_ocr_area),
        }

    def display_hotkey(self, action: str) -> str:
        """Pretty label for UI buttons (e.g. Ctrl+F9)."""
        raw = self.hotkey_map().get(action, "")
        return format_hotkey_display(raw)

    def pynput_hotkeys(self) -> dict[str, str]:
        """Map pynput GlobalHotKeys pattern → logical action name."""
        out: dict[str, str] = {}
        for action, chord in self.hotkey_map().items():
            pattern = to_pynput_hotkey(chord)
            if pattern:
                out[pattern] = action
        return out

    def control_key_names(self) -> set[str]:
        """Plain key names used in app chords (for recorder swallow with Ctrl)."""
        names: set[str] = set()
        for chord in self.hotkey_map().values():
            parts = [p for p in chord.split("+") if p and p not in ("ctrl", "alt", "shift", "win")]
            names.update(parts)
        return names

    def validate_hotkeys(self) -> str | None:
        """Return an error message if hotkeys collide or are empty."""
        seen: dict[str, str] = {}
        for action, chord in self.hotkey_map().items():
            if not chord:
                return f"Hotkey for {action} is empty"
            if chord in seen:
                return f"Hotkey conflict: {format_hotkey_display(chord)}"
            seen[chord] = action
        return None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> AppSettings:
        """Build settings from JSON dict with safe defaults."""
        base = cls()
        if not data:
            return base
        known = {f.name for f in fields(cls)}
        kwargs = {}
        for key, value in data.items():
            if key not in known:
                continue
            default = getattr(base, key)
            if key.startswith("hotkey_"):
                kwargs[key] = normalize_hotkey(str(value))
            elif isinstance(default, bool):
                kwargs[key] = bool(value)
            elif isinstance(default, int) and not isinstance(default, bool):
                try:
                    kwargs[key] = int(value)
                except (TypeError, ValueError):
                    kwargs[key] = default
            elif isinstance(default, float):
                try:
                    kwargs[key] = float(value)
                except (TypeError, ValueError):
                    kwargs[key] = default
            else:
                kwargs[key] = value
        merged = cls(**{**asdict(base), **kwargs})
        merged.mouse_move_ms = max(40, min(3000, int(merged.mouse_move_ms)))
        merged.mouse_curve = max(0.0, min(1.0, float(merged.mouse_curve)))
        merged.mouse_hover_ms = max(0, min(2000, int(merged.mouse_hover_ms)))
        return merged


# Cached in-process settings (set by load_settings / save_settings).
_current: AppSettings | None = None


def settings_path() -> Path:
    """Path to settings.json under the writable app root."""
    return project_root() / SETTINGS_FILENAME


def normalize_hotkey(value: str) -> str:
    """Normalize to lowercase plus-separated tokens, modifiers first."""
    raw = (value or "").strip().lower().replace(" ", "")
    if not raw:
        return ""
    raw = raw.replace("<", "").replace(">", "")
    parts = [p for p in raw.split("+") if p]
    aliases = {
        "control": "ctrl",
        "ctl": "ctrl",
        "cmd": "win",
        "super": "win",
        "option": "alt",
        "return": "enter",
        "esc": "escape",
    }
    norm = [aliases.get(p, p) for p in parts]
    mods = [p for p in ("ctrl", "alt", "shift", "win") if p in norm]
    keys = [p for p in norm if p not in ("ctrl", "alt", "shift", "win")]
    # Keep first non-modifier only for simple chords.
    if keys:
        return "+".join(mods + [keys[-1]])
    return "+".join(mods)


def format_hotkey_display(chord: str) -> str:
    """Turn ctrl+f9 into Ctrl+F9 for labels."""
    parts = normalize_hotkey(chord).split("+")
    pretty = []
    for p in parts:
        if not p:
            continue
        if p.startswith("f") and p[1:].isdigit():
            pretty.append(p.upper())
        else:
            pretty.append(p[:1].upper() + p[1:])
    return "+".join(pretty)


def to_pynput_hotkey(chord: str) -> str:
    """Convert ctrl+f9 → <ctrl>+<f9> for pynput GlobalHotKeys."""
    parts = normalize_hotkey(chord).split("+")
    if not parts or parts == [""]:
        return ""
    return "+".join(f"<{p}>" for p in parts)


def load_settings() -> AppSettings:
    """Load settings from disk (or defaults); cache as current."""
    global _current
    path = settings_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _current = AppSettings.from_dict(data if isinstance(data, dict) else {})
            return _current
        except Exception:
            pass
    _current = AppSettings()
    return _current


def get_settings() -> AppSettings:
    """Return cached settings, loading once if needed."""
    global _current
    if _current is None:
        return load_settings()
    return _current


def save_settings(settings: AppSettings) -> None:
    """Persist settings and update cache."""
    global _current
    path = settings_path()
    path.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
    _current = settings


def launch_command() -> str:
    """Command line used for Windows auto-start."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    main_py = project_root() / "main.py"
    py = Path(sys.executable).resolve()
    return f'"{py}" "{main_py.resolve()}"'


def apply_auto_start(enabled: bool) -> None:
    """Add or remove HKCU Run entry for Cat Autoclick (Windows)."""
    if sys.platform != "win32":
        return
    try:
        import winreg
    except ImportError:
        return
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, access) as key:
        if enabled:
            winreg.SetValueEx(key, _AUTO_START_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, _AUTO_START_NAME)
            except FileNotFoundError:
                pass


def read_auto_start_enabled() -> bool:
    """True if the HKCU Run entry currently exists."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_QUERY_VALUE) as key:
            winreg.QueryValueEx(key, _AUTO_START_NAME)
            return True
    except OSError:
        return False
