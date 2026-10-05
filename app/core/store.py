"""Load and save presets as JSON files under presets/."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from app.core.models import Preset


def project_root() -> Path:
    """Return the writable app root (repo root, or folder next to the .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_presets_dir() -> Path | None:
    """Return PyInstaller-bundled presets folder when running as a frozen app."""
    if not getattr(sys, "frozen", False):
        return None
    base = Path(getattr(sys, "_MEIPASS", ""))
    candidate = base / "presets"
    return candidate if candidate.is_dir() else None


def seed_bundled_presets(target: Path) -> None:
    """Copy bundled demo presets into the writable folder if it has none yet."""
    if any(target.glob("*.json")):
        return
    source = bundled_presets_dir()
    if source is None:
        return
    for path in source.glob("*.json"):
        shutil.copy2(path, target / path.name)


PROJECT_ROOT = project_root()
PRESETS_DIR = PROJECT_ROOT / "presets"


def _slug(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    return slug.strip("_") or "preset"


class PresetStore:
    """Filesystem-backed preset repository."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or PRESETS_DIR
        self.directory.mkdir(parents=True, exist_ok=True)
        seed_bundled_presets(self.directory)

    def list_presets(self) -> list[Preset]:
        """Load every *.json preset, sorted by name."""
        presets: list[Preset] = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                presets.append(self.load_file(path))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
        return presets

    def load_file(self, path: Path) -> Preset:
        with path.open("r", encoding="utf-8") as fh:
            return Preset.from_dict(json.load(fh))

    def path_for(self, preset: Preset) -> Path:
        return self.directory / f"{_slug(preset.name)}_{preset.id}.json"

    def save(self, preset: Preset) -> Path:
        """Persist preset; remove older files that shared the same id."""
        self._remove_by_id(preset.id)
        path = self.path_for(preset)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(preset.to_dict(), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        return path

    def delete(self, preset_id: str) -> None:
        self._remove_by_id(preset_id)

    def _remove_by_id(self, preset_id: str) -> None:
        for path in self.directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("id") == preset_id:
                path.unlink(missing_ok=True)

    def ensure_default(self) -> Preset:
        """Create a starter preset when the folder is empty."""
        existing = self.list_presets()
        if existing:
            return existing[0]
        preset = Preset(name="My First Macro")
        self.save(preset)
        return preset
