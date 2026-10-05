"""Screen capture, Thai/English OCR, and image template matching."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import mss
import numpy as np

from app.core.models import Action
from app.core.monitors import get_monitor
from app.core.store import project_root

_ocr_lock = threading.Lock()
_ocr_reader = None


@dataclass(frozen=True)
class CaptureSpec:
    """Where to capture: a full monitor or a rectangle in monitor-local coords."""

    monitor_index: int
    x: int = 0
    y: int = 0
    w: int = 0  # 0 = full width
    h: int = 0  # 0 = full height

    @classmethod
    def from_action(cls, action: Action, default_monitor: int) -> CaptureSpec:
        """Build a capture spec from action fields and preset monitor fallback."""
        mon = (
            int(action.capture_monitor)
            if action.capture_monitor is not None
            else default_monitor
        )
        return cls(
            monitor_index=mon,
            x=int(action.region_x or 0),
            y=int(action.region_y or 0),
            w=int(action.region_w or 0),
            h=int(action.region_h or 0),
        )


@dataclass(frozen=True)
class CaptureResult:
    """Captured BGR frame plus offsets to convert crop-local -> monitor-local."""

    image: np.ndarray
    offset_x: int
    offset_y: int
    monitor_index: int


@dataclass(frozen=True)
class TextHit:
    """One OCR match with monitor-local center coordinates."""

    text: str
    x: int
    y: int
    score: float


@dataclass(frozen=True)
class ImageHit:
    """One template match with monitor-local center coordinates."""

    x: int
    y: int
    score: float


def templates_dir() -> Path:
    """Writable folder for template images next to the app root."""
    path = project_root() / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_template_path(image_path: str) -> Path:
    """Resolve a template path (absolute or relative to templates/)."""
    raw = Path(image_path)
    if raw.is_file():
        return raw
    candidate = templates_dir() / image_path
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"Template not found: {image_path}")


def normalize_text(value: str) -> str:
    """Normalize whitespace for Thai/English contains matching."""
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def text_matches(haystack: str, needle: str) -> bool:
    """Return True if needle is contained in haystack after normalization."""
    n = normalize_text(needle)
    if not n:
        return False
    return n in normalize_text(haystack)


def capture_region(spec: CaptureSpec) -> CaptureResult:
    """Capture a full monitor or a sub-rectangle; coords are monitor-local."""
    mon = get_monitor(spec.monitor_index)
    x = max(0, spec.x)
    y = max(0, spec.y)
    w = spec.w if spec.w > 0 else mon.width - x
    h = spec.h if spec.h > 0 else mon.height - y
    w = max(1, min(w, mon.width - x))
    h = max(1, min(h, mon.height - y))
    region = {"left": mon.x + x, "top": mon.y + y, "width": w, "height": h}
    with mss.mss() as sct:
        shot = sct.grab(region)
    frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
    return CaptureResult(image=frame, offset_x=x, offset_y=y, monitor_index=spec.monitor_index)


def capture_monitor(monitor_index: int) -> np.ndarray:
    """Capture the selected monitor as a BGR numpy image."""
    return capture_region(CaptureSpec(monitor_index=monitor_index)).image


def is_ocr_enabled() -> bool:
    """Whether EasyOCR may load (from app settings)."""
    from app.core.settings import get_settings

    return bool(get_settings().ocr_enabled)


def _get_ocr_reader():
    """Lazy-load EasyOCR reader for Thai + English."""
    global _ocr_reader
    if not is_ocr_enabled():
        raise RuntimeError("OCR is disabled in Settings")
    if _ocr_reader is not None:
        return _ocr_reader
    with _ocr_lock:
        if _ocr_reader is not None:
            return _ocr_reader
        import easyocr  # heavy import — keep lazy

        _ocr_reader = easyocr.Reader(["th", "en"], gpu=False, verbose=False)
        return _ocr_reader


def find_text_boxes(
    monitor_index: int,
    query: str,
    *,
    image: np.ndarray | None = None,
    capture: CaptureSpec | None = None,
) -> list[TextHit]:
    """Find OCR boxes whose text contains query; coordinates are monitor-local."""
    if not is_ocr_enabled():
        return []
    if not normalize_text(query):
        return []
    offset_x = 0
    offset_y = 0
    if image is not None:
        frame = image
    else:
        spec = capture or CaptureSpec(monitor_index=monitor_index)
        result = capture_region(spec)
        frame = result.image
        offset_x = result.offset_x
        offset_y = result.offset_y
        monitor_index = result.monitor_index
    reader = _get_ocr_reader()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = reader.readtext(rgb)
    hits: list[TextHit] = []
    for box, text, score in results:
        if not text_matches(str(text), query):
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        cx = int((min(xs) + max(xs)) / 2) + offset_x
        cy = int((min(ys) + max(ys)) / 2) + offset_y
        hits.append(TextHit(text=str(text), x=cx, y=cy, score=float(score)))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


def find_template(
    monitor_index: int,
    image_path: str,
    threshold: float = 0.85,
    *,
    image: np.ndarray | None = None,
    capture: CaptureSpec | None = None,
) -> ImageHit | None:
    """Find the best template match; coordinates are monitor-local."""
    offset_x = 0
    offset_y = 0
    if image is not None:
        frame = image
    else:
        spec = capture or CaptureSpec(monitor_index=monitor_index)
        result = capture_region(spec)
        frame = result.image
        offset_x = result.offset_x
        offset_y = result.offset_y
    template = cv2.imread(str(resolve_template_path(image_path)), cv2.IMREAD_COLOR)
    if template is None:
        raise FileNotFoundError(f"Cannot read template image: {image_path}")
    if template.shape[0] > frame.shape[0] or template.shape[1] > frame.shape[1]:
        return None
    result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
    if float(max_val) < threshold:
        return None
    th, tw = template.shape[:2]
    cx = int(max_loc[0] + tw / 2) + offset_x
    cy = int(max_loc[1] + th / 2) + offset_y
    return ImageHit(x=cx, y=cy, score=float(max_val))


def screen_has_text(
    monitor_index: int,
    query: str,
    *,
    capture: CaptureSpec | None = None,
) -> bool:
    """Return True if query text is currently visible in the capture area."""
    return bool(find_text_boxes(monitor_index, query, capture=capture))


def screen_has_image(
    monitor_index: int,
    image_path: str,
    threshold: float = 0.85,
    *,
    capture: CaptureSpec | None = None,
) -> bool:
    """Return True if template is currently visible in the capture area."""
    return find_template(monitor_index, image_path, threshold, capture=capture) is not None
