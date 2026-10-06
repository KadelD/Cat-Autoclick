"""Space-dark visual tokens for Cat Autoclick.

Palette priority: black → navy → cyan → purple → white.
"""

from __future__ import annotations

# Surfaces
BG = "#070B14"
PANEL = "#0D1526"
PANEL_ALT = "#121C33"
BORDER = "#1E2A4A"
INPUT = "#0A1222"

# Accents
NAVY = "#152A55"
CYAN = "#4FC3F7"
CYAN_DIM = "#2A8BB8"
PURPLE = "#8B5CF6"
PURPLE_DIM = "#6D28D9"
WHITE = "#F4F7FF"
MUTED = "#8B97B8"

# Semantic
RECORD = "#E11D48"
RECORD_HOVER = "#BE123C"
STOP = "#334155"
STOP_HOVER = "#1E293B"
SUCCESS = "#34D399"

FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_SECTION = ("Segoe UI", 15, "bold")
FONT_BODY = ("Segoe UI", 13)
FONT_HINT = ("Segoe UI", 11)


def apply_app_theme() -> None:
    """Set CustomTkinter global appearance for the space theme."""
    import customtkinter as ctk

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
