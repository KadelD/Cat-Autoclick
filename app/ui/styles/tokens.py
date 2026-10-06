"""Design tokens — single source of truth for Cat Automation Studio UI."""

from __future__ import annotations


class Colors:
    """Professional dark IDE palette."""

    APP_BG = "#080C12"
    PANEL = "#0D131D"
    SURFACE = "#111927"
    SURFACE_HOVER = "#162033"
    SURFACE_SELECTED = "#172A46"
    INPUT = "#0C1420"

    BORDER = "#1E293B"
    BORDER_STRONG = "#2A3A4F"
    BORDER_FOCUS = "#3B82F6"

    TEXT = "#E6EDF7"
    TEXT_SECONDARY = "#9AA8BA"
    TEXT_MUTED = "#64748B"
    TEXT_DISABLED = "#475569"

    ACCENT = "#3B82F6"
    ACCENT_HOVER = "#2563EB"
    ACCENT_PRESSED = "#1D4ED8"
    ACCENT_SOFT = "rgba(59, 130, 246, 0.14)"
    ACCENT_SOFT_BORDER = "rgba(59, 130, 246, 0.45)"

    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    RECORD = "#EF4444"
    INFO = "#38BDF8"

    # Legacy aliases used by older modules
    BG = APP_BG
    PANEL_ALT = SURFACE
    GUIDE = ACCENT


class Space:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Radius:
    SM = 4
    MD = 6
    LG = 8


class Control:
    HEIGHT = 32
    HEIGHT_SM = 28
    HEIGHT_LG = 36
    ICON = 16
    ICON_SM = 14
    ICON_LG = 18
    BTN_ICON = 28


class Font:
    FAMILY = '"Inter", "Segoe UI", system-ui, sans-serif'
    TITLE = 14
    SECTION = 11
    BODY = 13
    BODY_SM = 12
    META = 11
    BUTTON = 12
