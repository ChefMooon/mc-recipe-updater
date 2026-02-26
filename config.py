"""
ConfigManager - Handles loading, saving, and managing sync profiles.

User data is stored under ~/.mcru/:
  ~/.mcru/profiles.json         — saved sync profiles
  ~/.mcru/mapping-presets.json   — mapping presets (seeded from package defaults)
  ~/.mcru/reports/               — timestamped run reports

Each profile looks like:
{
    "name": "myproject",
    "source": "/path/to/source",
    "target": "/path/to/target",
    "parsers": ["normalize_line_endings"],
    "description": "My project sync",
    "created_at": "2024-01-15T10:30:00"
}
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime


CONFIG_DIR = Path.home() / ".mcru"
CONFIG_FILE = CONFIG_DIR / "profiles.json"
BUNDLED_MAPPING_FILE = Path(__file__).resolve().parent / "mapping-presets.json"
DEFAULT_MAPPING_FILE = CONFIG_DIR / "mapping-presets.json"


class ConfigManager:
    def __init__(self):
        self._ensure_config_dir()
        self.profiles = self._load()

    def _ensure_config_dir(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(json.dumps({"profiles": []}, indent=2))
        if not DEFAULT_MAPPING_FILE.exists() and BUNDLED_MAPPING_FILE.exists():
            shutil.copy2(BUNDLED_MAPPING_FILE, DEFAULT_MAPPING_FILE)

    def _load(self):
        data = json.loads(CONFIG_FILE.read_text())
        return data.get("profiles", [])

    def _save(self):
        CONFIG_FILE.write_text(json.dumps({"profiles": self.profiles}, indent=2))

    def add_profile(
        self,
        name: str,
        source: str,
        target: str,
        parsers: list,
        description: str = "",
        mapping_preset: str | None = None,
    ):
        # Remove existing profile with the same name (upsert)
        self.profiles = [p for p in self.profiles if p["name"] != name]
        profile = {
            "name": name,
            "source": str(Path(source).resolve()),
            "target": str(Path(target).resolve()),
            "parsers": parsers,
            "description": description,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        if mapping_preset:
            profile["mapping_preset"] = mapping_preset
        self.profiles.append(profile)
        self._save()

    def remove_profile(self, name: str):
        before = len(self.profiles)
        self.profiles = [p for p in self.profiles if p["name"] != name]
        if len(self.profiles) == before:
            raise ValueError(f"Profile '{name}' not found.")
        self._save()

    def get_profile(self, name: str) -> dict | None:
        for p in self.profiles:
            if p["name"] == name:
                return dict(p)  # return a copy
        return None

    def list_profiles(self) -> list:
        return list(self.profiles)

    def get_mapping_preset(self, name: str, mapping_file: str | None = None) -> dict:
        mapping_path = self._resolve_mapping_file(mapping_file)

        if not mapping_path.exists():
            raise FileNotFoundError(
                f"Mapping file not found: {mapping_path}. "
                "Expected at ~/.mcru/mapping-presets.json. "
                "You can also set MCRU_MAPPING_FILE to override."
            )

        data = json.loads(mapping_path.read_text())
        presets = data.get("presets", {})
        if name not in presets:
            available = ", ".join(sorted(presets.keys())) or "none"
            raise ValueError(
                f"Mapping preset '{name}' not found in {mapping_path}. "
                f"Available presets: {available}"
            )

        preset = presets[name]
        required_keys = ["source_roots", "target_roots", "category_map", "omit_globs", "rules"]
        missing = [key for key in required_keys if key not in preset]
        if missing:
            raise ValueError(
                f"Mapping preset '{name}' is missing keys: {', '.join(missing)}"
            )

        return dict(preset)

    def _resolve_mapping_file(self, mapping_file: str | None = None) -> Path:
        env_mapping_file = os.getenv("MCRU_MAPPING_FILE")
        candidate = mapping_file or env_mapping_file
        if candidate:
            return Path(candidate).expanduser().resolve()
        return DEFAULT_MAPPING_FILE
