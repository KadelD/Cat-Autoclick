"""Load and save presets as JSON files under presets/."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.models import Preset

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRESETS_DIR = PROJECT_ROOT / "presets"


def _slug(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    return slug.strip("_") or "preset"


class PresetStore:
    """Filesystem-backed preset repository."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or PRESETS_DIR
        self.directory.mkdir(parents=True, exist_ok=True)

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
