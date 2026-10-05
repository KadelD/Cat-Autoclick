"""Google Material Icons font helpers for action-row glyphs."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import customtkinter as ctk

_FAMILY = "Material Icons"
_registered = False


def _assets_fonts() -> Path:
    """Return folder that holds MaterialIcons-Regular.ttf."""
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        bundled = meipass / "assets" / "fonts"
        if bundled.is_dir():
            return bundled
        return Path(sys.executable).resolve().parent / "assets" / "fonts"
    return Path(__file__).resolve().parents[2] / "assets" / "fonts"


def _font_path() -> Path:
    return _assets_fonts() / "MaterialIcons-Regular.ttf"


def _codepoints_path() -> Path:
    return _assets_fonts() / "MaterialIcons-Regular.codepoints"


@lru_cache(maxsize=1)
def _codepoints() -> dict[str, str]:
    """Load name -> unicode hex map from the Material Icons codepoints file."""
    path = _codepoints_path()
    mapping: dict[str, str] = {}
    if not path.is_file():
        return mapping
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) == 2:
            mapping[parts[0]] = parts[1]
    return mapping


def ensure_material_icons() -> bool:
    """Register the bundled Material Icons font once. Returns True if available."""
    global _registered
    if _registered:
        return _font_path().is_file()
    path = _font_path()
    if not path.is_file():
        return False
    try:
        if sys.platform == "win32":
            import ctypes

            # FR_PRIVATE: load for this process only (no system install).
            FR_PRIVATE = 0x10
            ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
        _registered = True
        return True
    except Exception:
        return False


def glyph(name: str, fallback: str = "•") -> str:
    """Return the Material Icons character for a ligature/icon name."""
    code = _codepoints().get(name)
    if code is None:
        return fallback
    try:
        return chr(int(code, 16))
    except ValueError:
        return fallback


_font_cache: dict[int, ctk.CTkFont] = {}


def material_font(size: int = 18) -> ctk.CTkFont:
    """Return a cached CTk font using Material Icons when the TTF is available."""
    cached = _font_cache.get(size)
    if cached is not None:
        return cached
    if ensure_material_icons():
        font = ctk.CTkFont(family=_FAMILY, size=size)
    else:
        font = ctk.CTkFont(size=size)
    _font_cache[size] = font
    return font
