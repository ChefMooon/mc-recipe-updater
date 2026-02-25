"""
ConfigManager - Handles loading, saving, and managing sync profiles.

Profiles are stored in a JSON file at:
  ~/.foldersyncer/profiles.json

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
from pathlib import Path
from datetime import datetime


CONFIG_DIR = Path.home() / ".foldersyncer"
CONFIG_FILE = CONFIG_DIR / "profiles.json"


class ConfigManager:
    def __init__(self):
        self._ensure_config_dir()
        self.profiles = self._load()

    def _ensure_config_dir(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(json.dumps({"profiles": []}, indent=2))

    def _load(self):
        data = json.loads(CONFIG_FILE.read_text())
        return data.get("profiles", [])

    def _save(self):
        CONFIG_FILE.write_text(json.dumps({"profiles": self.profiles}, indent=2))

    def add_profile(self, name: str, source: str, target: str, parsers: list, description: str = ""):
        # Remove existing profile with the same name (upsert)
        self.profiles = [p for p in self.profiles if p["name"] != name]
        self.profiles.append({
            "name": name,
            "source": str(Path(source).resolve()),
            "target": str(Path(target).resolve()),
            "parsers": parsers,
            "description": description,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
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
