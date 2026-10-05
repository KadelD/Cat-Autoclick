"""Enumerate displays and map coordinates relative to a chosen monitor."""

from __future__ import annotations

from dataclasses import dataclass

from screeninfo import get_monitors


@dataclass(frozen=True)
class MonitorInfo:
    """One physical/logical display."""

    index: int
    name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool

    @property
    def label(self) -> str:
        primary = " (primary)" if self.is_primary else ""
        return f"{self.index}: {self.width}x{self.height} @ ({self.x},{self.y}){primary}"


def list_monitors() -> list[MonitorInfo]:
    """Return monitors in screeninfo order with stable indices."""
    result: list[MonitorInfo] = []
    for i, m in enumerate(get_monitors()):
        name = getattr(m, "name", None) or f"Display {i}"
        result.append(
            MonitorInfo(
                index=i,
                name=name,
                x=int(m.x),
                y=int(m.y),
                width=int(m.width),
                height=int(m.height),
                is_primary=bool(getattr(m, "is_primary", False)),
            )
        )
    if not result:
        # Fallback single virtual desktop if enumeration fails.
        result.append(
            MonitorInfo(
                index=0,
                name="Primary",
                x=0,
                y=0,
                width=1920,
                height=1080,
                is_primary=True,
            )
        )
    return result


def get_monitor(index: int) -> MonitorInfo:
    """Resolve monitor by index, clamping to available range."""
    monitors = list_monitors()
    if index < 0 or index >= len(monitors):
        return monitors[0]
    return monitors[index]


def to_global(monitor_index: int, x: int, y: int) -> tuple[int, int]:
    """Convert monitor-local coordinates to virtual-desktop global coords."""
    mon = get_monitor(monitor_index)
    return mon.x + x, mon.y + y


def to_local(monitor_index: int, global_x: int, global_y: int) -> tuple[int, int]:
    """Convert global coords to monitor-local coords for the chosen display."""
    mon = get_monitor(monitor_index)
    return global_x - mon.x, global_y - mon.y


def monitor_containing(global_x: int, global_y: int) -> MonitorInfo | None:
    """Find which monitor contains a global point, if any."""
    for mon in list_monitors():
        if mon.x <= global_x < mon.x + mon.width and mon.y <= global_y < mon.y + mon.height:
            return mon
    return None
