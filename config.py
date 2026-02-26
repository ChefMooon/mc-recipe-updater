"""
ConfigManager - Handles loading, saving, and managing sync profiles and suites.

User data is stored under ~/.mcru/:
  ~/.mcru/profiles.json         — saved sync profiles
  ~/.mcru/suites.json           — saved suites (groups of profiles)
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

Each suite looks like:
{
    "name": "full-sync",
    "description": "Sync all mods in order",
    "created_at": "2024-01-15T10:30:00",
    "profiles": ["mod-a", "mod-b", "mod-c"]
}
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime


CONFIG_DIR = Path.home() / ".mcru"
CONFIG_FILE = CONFIG_DIR / "profiles.json"
SUITES_FILE = CONFIG_DIR / "suites.json"
BUNDLED_MAPPING_FILE = Path(__file__).resolve().parent / "mapping-presets.json"
DEFAULT_MAPPING_FILE = CONFIG_DIR / "mapping-presets.json"


class ConfigManager:
    def __init__(self):
        self._ensure_config_dir()
        self.profiles = self._load()
        self.suites = self._load_suites()

    def _ensure_config_dir(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(json.dumps({"profiles": []}, indent=2))
        if not SUITES_FILE.exists():
            SUITES_FILE.write_text(json.dumps({"suites": []}, indent=2))
        if not DEFAULT_MAPPING_FILE.exists() and BUNDLED_MAPPING_FILE.exists():
            shutil.copy2(BUNDLED_MAPPING_FILE, DEFAULT_MAPPING_FILE)

    def _load(self):
        data = json.loads(CONFIG_FILE.read_text())
        return data.get("profiles", [])

    def _save(self):
        CONFIG_FILE.write_text(json.dumps({"profiles": self.profiles}, indent=2))

    def _load_suites(self) -> list:
        data = json.loads(SUITES_FILE.read_text())
        return data.get("suites", [])

    def _save_suites(self):
        SUITES_FILE.write_text(json.dumps({"suites": self.suites}, indent=2))

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

    # ──────────────────────────────────────────────
    # Suite management
    # ──────────────────────────────────────────────

    def list_suites(self) -> list:
        return list(self.suites)

    def get_suite(self, name: str) -> dict | None:
        for s in self.suites:
            if s["name"] == name:
                return dict(s)
        return None

    def _get_suite_mutable(self, name: str) -> dict:
        """Return the live suite dict (not a copy) for in-place mutation."""
        for s in self.suites:
            if s["name"] == name:
                return s
        raise ValueError(f"Suite '{name}' not found.")

    def save_suite(self, name: str, description: str = "", profiles: list | None = None):
        """Create or overwrite a suite by name. Preserves profile list and created_at if not supplied."""
        existing = self.get_suite(name)
        current_profiles = existing["profiles"] if existing else []
        original_created_at = existing["created_at"] if existing else datetime.now().isoformat(timespec="seconds")
        self.suites = [s for s in self.suites if s["name"] != name]
        suite = {
            "name": name,
            "description": description,
            "created_at": original_created_at,
            "profiles": profiles if profiles is not None else current_profiles,
        }
        self.suites.append(suite)
        self._save_suites()

    def update_suite_description(self, name: str, description: str):
        """Update only the description of an existing suite."""
        suite = self._get_suite_mutable(name)
        suite["description"] = description
        self._save_suites()

    def delete_suite(self, name: str):
        before = len(self.suites)
        self.suites = [s for s in self.suites if s["name"] != name]
        if len(self.suites) == before:
            raise ValueError(f"Suite '{name}' not found.")
        self._save_suites()

    def add_profile_to_suite(self, suite_name: str, profile_name: str):
        suite = self._get_suite_mutable(suite_name)
        if self.get_profile(profile_name) is None:
            raise ValueError(f"Profile '{profile_name}' not found.")
        if profile_name in suite["profiles"]:
            raise ValueError(f"Profile '{profile_name}' is already in suite '{suite_name}'.")
        suite["profiles"].append(profile_name)
        self._save_suites()

    def remove_profile_from_suite(self, suite_name: str, profile_name: str):
        suite = self._get_suite_mutable(suite_name)
        if profile_name not in suite["profiles"]:
            raise ValueError(f"Profile '{profile_name}' is not in suite '{suite_name}'.")
        suite["profiles"].remove(profile_name)
        self._save_suites()

    def reorder_profile_in_suite(self, suite_name: str, profile_name: str, position: int):
        """Move profile_name to a 1-based position within the suite's profile list."""
        suite = self._get_suite_mutable(suite_name)
        if profile_name not in suite["profiles"]:
            raise ValueError(f"Profile '{profile_name}' is not in suite '{suite_name}'.")
        suite["profiles"].remove(profile_name)
        idx = max(0, min(position - 1, len(suite["profiles"])))
        suite["profiles"].insert(idx, profile_name)
        self._save_suites()

    # ──────────────────────────────────────────────
    # Mapping presets
    # ──────────────────────────────────────────────

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
