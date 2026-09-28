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
import re
import shutil
import copy
from pathlib import Path
from datetime import datetime, timedelta


CONFIG_DIR = Path.home() / ".mcru"
CONFIG_FILE = CONFIG_DIR / "profiles.json"
SUITES_FILE = CONFIG_DIR / "suites.json"
GLOBAL_CONFIG_FILE = CONFIG_DIR / "config.json"
BUNDLED_MAPPING_FILE = Path(__file__).resolve().parent / "mapping-presets.json"
DEFAULT_MAPPING_FILE = CONFIG_DIR / "mapping-presets.json"
REPORTS_DIR = CONFIG_DIR / "reports"


class ConfigManager:
    def __init__(self):
        self.recovery_errors: list[str] = []
        self._profiles_load_error: str | None = None
        self._suites_load_error: str | None = None
        try:
            self._ensure_config_dir()
        except OSError as err:
            self.recovery_errors.append(f"Could not prepare configuration directory: {err}")
        try:
            self.profiles = self._load()
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as err:
            self._profiles_load_error = str(err)
            self.profiles = []
            self.recovery_errors.append(f"Profiles were not loaded; {CONFIG_FILE} was preserved: {err}")
        try:
            self.suites = self._load_suites()
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as err:
            self._suites_load_error = str(err)
            self.suites = []
            self.recovery_errors.append(f"Suites were not loaded; {SUITES_FILE} was preserved: {err}")

    def _ensure_config_dir(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(json.dumps({"profiles": []}, indent=2), encoding="utf-8")
        if not SUITES_FILE.exists():
            SUITES_FILE.write_text(json.dumps({"suites": []}, indent=2), encoding="utf-8")
        if not DEFAULT_MAPPING_FILE.exists() and BUNDLED_MAPPING_FILE.exists():
            shutil.copy2(BUNDLED_MAPPING_FILE, DEFAULT_MAPPING_FILE)

    def _load(self):
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
            raise ValueError("expected a JSON object containing a profiles list")
        if any(not isinstance(profile, dict) for profile in data["profiles"]):
            raise ValueError("profiles must contain JSON objects")
        return data["profiles"]

    def _save(self):
        if self._profiles_load_error:
            raise RuntimeError(f"Cannot save profiles while the original file is invalid: {CONFIG_FILE}")
        # Prepare profiles for saving, omitting empty optional fields
        profiles_to_save = []
        for profile in self.profiles:
            profile_copy = dict(profile)
            # Omit tags if empty array
            if "tags" in profile_copy and not profile_copy["tags"]:
                profile_copy.pop("tags", None)
            profiles_to_save.append(profile_copy)
        CONFIG_FILE.write_text(json.dumps({"profiles": profiles_to_save}, indent=2), encoding="utf-8")

    def _load_suites(self) -> list:
        data = json.loads(SUITES_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("suites"), list):
            raise ValueError("expected a JSON object containing a suites list")
        if any(not isinstance(suite, dict) for suite in data["suites"]):
            raise ValueError("suites must contain JSON objects")
        return data["suites"]

    def _save_suites(self):
        if self._suites_load_error:
            raise RuntimeError(f"Cannot save suites while the original file is invalid: {SUITES_FILE}")
        SUITES_FILE.write_text(json.dumps({"suites": self.suites}, indent=2), encoding="utf-8")

    def add_profile(
        self,
        name: str,
        source: str,
        target: str,
        parsers: list,
        description: str = "",
        mapping_preset: str | None = None,
        target_changelog: bool = False,
    ):
        """Create a new profile or overwrite an existing one by name.

        Args:
            name: Unique profile identifier.
            source: Path to source folder (will be resolved to absolute path).
            target: Path to target folder (will be resolved to absolute path).
            parsers: List of content parser names to apply before hashing.
            description: Optional description shown in profile list.
            mapping_preset: Optional mapping preset name for category-based sync.
            target_changelog: If True, append Markdown changelog entry to target CHANGELOG.md.

        The profile is initialized with an empty tags list (optional field, omitted when saving if empty).
        Call update_profile_field with 'add-tag' to add tags after profile creation.
        """
        # Remove existing profile with the same name (upsert)
        self.profiles = [p for p in self.profiles if p["name"] != name]
        profile = {
            "name": name,
            "source": str(Path(source).resolve()),
            "target": str(Path(target).resolve()),
            "parsers": parsers,
            "description": description,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "tags": [],  # Initialize as empty list (will be omitted when saving if empty)
        }
        if mapping_preset:
            profile["mapping_preset"] = mapping_preset
        if target_changelog:
            profile["target_changelog"] = True
        self.profiles.append(profile)
        self._save()

    def remove_profile(self, name: str):
        before = len(self.profiles)
        self.profiles = [p for p in self.profiles if p["name"] != name]
        if len(self.profiles) == before:
            raise ValueError(f"Profile '{name}' not found.")
        self._save()

    def rename_profile(self, old_name: str, new_name: str):
        """Rename a profile and update all suite references.

        Args:
            old_name: Existing profile name.
            new_name: Desired profile name.
        """
        old_name = old_name.strip()
        new_name = new_name.strip()

        if not new_name:
            raise ValueError("Profile name cannot be empty.")

        profile = self._get_profile_mutable(old_name)
        if old_name == new_name:
            return

        if self.get_profile(new_name) is not None:
            raise ValueError(f"Profile '{new_name}' already exists.")

        profile["name"] = new_name

        for suite in self.suites:
            suite_profiles = suite.get("profiles", [])
            suite["profiles"] = [new_name if name == old_name else name for name in suite_profiles]

        self._save()
        self._save_suites()

    def get_profile(self, name: str) -> dict | None:
        for p in self.profiles:
            if p["name"] == name:
                profile_copy = dict(p)
                # Ensure tags field exists (backward compatibility with old profiles)
                if "tags" not in profile_copy:
                    profile_copy["tags"] = []
                return profile_copy
        return None

    def list_profiles(self) -> list:
        return list(self.profiles)

    def sort_profiles(self, sort_by: str = "name", order: str = "asc", dry_run: bool = False) -> dict:
        """Sort profiles by a given field and order.

        Args:
            sort_by: Field to sort by. One of: 'name', 'created_at'.
            order:   Sort direction. One of: 'asc', 'desc'.
            dry_run: If True, return the sorted list without modifying or saving.

        Returns:
            dict with keys: sort_by, order, dry_run, profiles (sorted copy).
        """
        valid_sort_by = ("name", "created_at")
        valid_order = ("asc", "desc")
        if sort_by not in valid_sort_by:
            raise ValueError(f"Invalid sort_by '{sort_by}'. Choose from: {', '.join(valid_sort_by)}")
        if order not in valid_order:
            raise ValueError(f"Invalid order '{order}'. Choose from: {', '.join(valid_order)}")

        reverse = order == "desc"

        def sort_key(p):
            if sort_by == "created_at":
                return p.get("created_at") or ""
            return p.get("name", "").lower()

        sorted_profiles = sorted(self.profiles, key=sort_key, reverse=reverse)

        if not dry_run:
            self.profiles = sorted_profiles
            self._save()

        return {
            "sort_by": sort_by,
            "order": order,
            "dry_run": dry_run,
            "profiles": sorted_profiles,
        }

    def list_profiles_by_tags(self, tag_groups: list) -> list:
        """Filter profiles by tags with AND/OR logic support.

        Args:
            tag_groups: List of tag group strings. Examples:
                - ["fabric"] → profiles with tag "fabric"
                - ["fabric", "forge"] → profiles with "fabric" OR "forge" (OR between groups)
                - ["fabric,priority-high"] → profiles with "fabric" OR "priority-high" (OR within group)
                - ["fabric,priority-high,+and"] → profiles with BOTH "fabric" AND "priority-high"

        Logic:
            - Default is OR between groups (multiple tag_groups strings)
            - Within a group (comma-separated tags), default is OR
            - Append ",+and" to a group to use AND logic within that group
            - Tags are normalized to lowercase for comparison

        Returns:
            List of profiles matching the filter criteria, in original order.
        """
        # Empty tag list returns all profiles
        if not tag_groups:
            return list(self.profiles)

        matched_profiles = []

        for profile in self.profiles:
            profile_tags = set(profile.get("tags", []))
            
            # Check if profile matches any of the tag groups (OR between groups)
            matches_any_group = False
            
            for group in tag_groups:
                # Parse group: check for +and suffix
                use_and = group.endswith(",+and")
                if use_and:
                    # Remove the ",+and" suffix to get the actual tags
                    group = group[:-4]
                
                # Split by comma to get individual tags in this group
                group_tags = [self._normalize_tag(t.strip()) for t in group.split(",")]
                # Filter out empty strings
                group_tags = [t for t in group_tags if t]
                
                if not group_tags:
                    continue
                
                # Check if profile matches this group
                if use_and:
                    # AND logic: profile must have ALL tags in the group
                    matches_group = all(tag in profile_tags for tag in group_tags)
                else:
                    # OR logic: profile must have at least ONE tag in the group
                    matches_group = any(tag in profile_tags for tag in group_tags)
                
                if matches_group:
                    matches_any_group = True
                    break
            
            if matches_any_group:
                matched_profiles.append(profile)

        return matched_profiles

    def _get_profile_mutable(self, name: str) -> dict:
        """Return the live profile dict (not a copy) for in-place mutation."""
        for p in self.profiles:
            if p["name"] == name:
                # Ensure tags field exists (backward compatibility)
                if "tags" not in p:
                    p["tags"] = []
                return p
        raise ValueError(f"Profile '{name}' not found.")

    def _normalize_tag(self, tag: str) -> str:
        """Normalize a tag to lowercase for case-insensitive comparison and storage."""
        return tag.lower()

    def update_profile_field(self, name: str, field: str, value):
        """Update a single field of an existing profile without touching others.
        
        Args:
            name: Profile name to update.
            field: Field to update. Supported fields:
                - 'description': Profile description (string).
                - 'mapping_preset': Mapping preset name (string), or None to remove.
                - 'target_changelog': Boolean to enable/disable changelog.
                - 'source': Source folder path (string).
                - 'target': Target folder path (string).
                - 'parsers': List of parser names (replaces existing list).
                - 'add-tag': Add a single tag (normalized to lowercase).
                - 'remove-tag': Remove a single tag (normalized to lowercase).
            value: New value for the field.

        Tags are case-insensitive; 'add-tag' and 'remove-tag' operations normalize to lowercase.
        """
        profile = self._get_profile_mutable(name)
        
        if field == "description":
            profile["description"] = value
        elif field == "mapping_preset":
            if value is None:
                profile.pop("mapping_preset", None)
            else:
                profile["mapping_preset"] = value
        elif field == "target_changelog":
            if value:
                profile["target_changelog"] = True
            else:
                profile.pop("target_changelog", None)
        elif field == "source":
            profile["source"] = str(Path(value).resolve())
        elif field == "target":
            profile["target"] = str(Path(value).resolve())
        elif field == "parsers":
            profile["parsers"] = list(value) if value else []
        elif field == "add-tag":
            normalized_tag = self._normalize_tag(value)
            if normalized_tag not in profile["tags"]:
                profile["tags"].append(normalized_tag)
        elif field == "remove-tag":
            normalized_tag = self._normalize_tag(value)
            if normalized_tag in profile["tags"]:
                profile["tags"].remove(normalized_tag)
        else:
            raise ValueError(f"Cannot update field '{field}'. Supported fields: description, mapping_preset, target_changelog, source, target, parsers, add-tag, remove-tag")
        
        self._save()

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


# ──────────────────────────────────────────────
# Report Manager
# ──────────────────────────────────────────────

REPORTS_DIR = Path.home() / ".mcru" / "reports"


class ReportManager:
    """Manages saved run reports in ~/.mcru/reports/."""

    _FILENAME_PATTERN = re.compile(r"^(.+)_(\d{8}_\d{6})\.txt$")

    @staticmethod
    def _parse_report(path: Path) -> dict:
        """Extract profile/suite name and timestamp from a report Path."""
        match = ReportManager._FILENAME_PATTERN.match(path.name)
        if match:
            profile_name = match.group(1)
            try:
                timestamp = datetime.strptime(match.group(2), "%Y%m%d_%H%M%S")
            except ValueError:
                timestamp = None
        else:
            profile_name = path.stem
            timestamp = None
        size = path.stat().st_size if path.exists() else 0
        return {
            "path": path,
            "name": profile_name,
            "timestamp": timestamp,
            "size": size,
            "filename": path.name,
        }

    def list_reports(self, limit: int | None = None, sort_by: str = "date") -> list[dict]:
        """Return report info dicts, sorted newest-first by default."""
        if not REPORTS_DIR.exists():
            return []
        reports = [self._parse_report(p) for p in REPORTS_DIR.glob("*.txt")]
        if sort_by == "name":
            reports.sort(key=lambda r: (r["name"] or "").lower())
        elif sort_by == "size":
            reports.sort(key=lambda r: r["size"], reverse=True)
        else:  # date (default)
            reports.sort(key=lambda r: r["timestamp"] or datetime.min, reverse=True)
        if limit is not None:
            reports = reports[:limit]
        return reports

    def find_report(self, name: str) -> Path | None:
        """Locate a report file by exact filename or stem. Returns Path or None."""
        if not REPORTS_DIR.exists():
            return None
        # exact filename match
        exact = REPORTS_DIR / name
        if exact.exists():
            return exact
        # try adding .txt extension
        with_ext = REPORTS_DIR / (name if name.endswith(".txt") else name + ".txt")
        if with_ext.exists():
            return with_ext
        return None

    def search_reports(self, query: str) -> list[dict]:
        """Return reports whose profile/suite name contains query (case-insensitive)."""
        q = query.lower()
        return [r for r in self.list_reports() if q in (r["name"] or "").lower()]

    def delete_report(self, path: Path) -> None:
        """Delete a single report file."""
        path.unlink()

    def prune_reports(
        self,
        keep_count: int | None = None,
        older_than_days: int | None = None,
        delete_all: bool = False,
        dry_run: bool = False,
    ) -> dict:
        """Delete reports by criteria. Strategies are additive (union). Returns summary."""
        all_reports = self.list_reports()  # newest first
        to_delete: set[Path] = set()

        if delete_all:
            to_delete = {r["path"] for r in all_reports}
        else:
            if keep_count is not None:
                for r in all_reports[keep_count:]:
                    to_delete.add(r["path"])
            if older_than_days is not None:
                cutoff = datetime.now() - timedelta(days=older_than_days)
                for r in all_reports:
                    if r["timestamp"] and r["timestamp"] < cutoff:
                        to_delete.add(r["path"])

        deleted: list[Path] = []
        space_freed = 0
        for path in sorted(to_delete, key=lambda p: p.name):
            space_freed += path.stat().st_size if path.exists() else 0
            if not dry_run:
                path.unlink()
            deleted.append(path)

        return {"deleted": deleted, "space_freed": space_freed, "dry_run": dry_run}


class GlobalConfig:
    """Manages global mcru settings stored in ~/.mcru/config.json."""

    DEFAULT_CONFIG = {
        "backup": {
            "enabled": True,
            "max_backups": 10,
        }
    }

    def __init__(self):
        self.load_error: str | None = None
        try:
            self._ensure_config_file()
        except OSError as err:
            self.load_error = str(err)

    def _ensure_config_file(self):
        """Create global config file if it doesn't exist."""
        if not GLOBAL_CONFIG_FILE.exists():
            GLOBAL_CONFIG_FILE.write_text(json.dumps(self.DEFAULT_CONFIG, indent=2))

    def load(self) -> dict:
        """Load and return the entire global config."""
        try:
            data = json.loads(GLOBAL_CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            backup = data.get("backup", {})
            if not isinstance(backup, dict):
                raise ValueError("'backup' must be a JSON object")
            if "enabled" in backup and not isinstance(backup["enabled"], bool):
                raise ValueError("'backup.enabled' must be true or false")
            if "max_backups" in backup and (
                not isinstance(backup["max_backups"], int)
                or isinstance(backup["max_backups"], bool)
                or backup["max_backups"] < 0
            ):
                raise ValueError("'backup.max_backups' must be a non-negative integer")
            self.load_error = None
            return data
        except FileNotFoundError:
            return copy.deepcopy(self.DEFAULT_CONFIG)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as err:
            self.load_error = f"{GLOBAL_CONFIG_FILE} was preserved: {err}"
            return copy.deepcopy(self.DEFAULT_CONFIG)

    def save(self, config: dict):
        """Save the global config."""
        GLOBAL_CONFIG_FILE.write_text(json.dumps(config, indent=2))

    def get(self, key_path: str, default=None):
        """
        Get a config value by dot-separated path.
        Example: get("backup.enabled") returns True/False
        """
        config = self.load()
        keys = key_path.split(".")
        value = config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        return value if value is not None else default

    def set(self, key_path: str, value):
        """
        Set a config value by dot-separated path.
        Example: set("backup.enabled", False)
        """
        config = self.load()
        keys = key_path.split(".")

        # Navigate/create the path
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set the final value
        current[keys[-1]] = value
        self.save(config)
