"""
BackupManager - Handles backup creation, rotation, restoration, and management.

User backups are stored under ~/.mcru/backups/:
  ~/.mcru/backups/                    — timestamped .zip snapshot files
  ~/.mcru/backups.json                — backup metadata registry

Each backup is a full snapshot of the target folder taken before a sync run.
Backups are named: backup_<profile-or-"quick">_<YYYYMMDD_HHMMSS>.zip

Backup metadata (backups.json) schema:
[
  {
    "id": "backup_recipes_20250307_143022",
    "filename": "backup_recipes_20250307_143022.zip",
    "profile": "recipes",
    "target": "/path/to/target/folder",
    "created_at": "2025-03-07T14:30:22",
    "run_result": "pending",
    "pinned": false,
    "note": ""
  }
]
"""

import json
import zipfile
import shutil
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)

BACKUPS_DIR = Path.home() / ".mcru" / "backups"
BACKUPS_REGISTRY = Path.home() / ".mcru" / "backups.json"


@dataclass
class BackupEntry:
    """Represents a backup metadata entry."""
    id: str
    filename: str
    profile: str
    target: str
    created_at: str
    run_result: str  # "pending", "success", "failed"
    pinned: bool = False
    note: str = ""

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "BackupEntry":
        """Create from dictionary."""
        return BackupEntry(**data)


class BackupManager:
    """Manages backup creation, rotation, restoration, and metadata."""

    def __init__(self):
        """Initialize BackupManager and ensure directories/files exist."""
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        """Ensure backup directory exists and backups.json is initialized."""
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        if not BACKUPS_REGISTRY.exists():
            BACKUPS_REGISTRY.write_text(json.dumps([], indent=2))

    def _generate_backup_id(self, profile_name: str) -> str:
        """Generate a unique backup ID using profile name and timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"backup_{profile_name}_{timestamp}"

    def _load_registry(self) -> list[BackupEntry]:
        """Load backup metadata from backups.json."""
        try:
            data = json.loads(BACKUPS_REGISTRY.read_text())
            if not isinstance(data, list):
                logger.warning("backups.json is malformed (not a list), reinitializing")
                return []
            return [BackupEntry.from_dict(entry) for entry in data]
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"backups.json is malformed: {e}, reinitializing")
            return []

    def _save_registry(self, entries: list[BackupEntry]):
        """Save backup metadata to backups.json."""
        data = [entry.to_dict() for entry in entries]
        BACKUPS_REGISTRY.write_text(json.dumps(data, indent=2))

    def create_backup(self, target_path: str, profile_name: str) -> str:
        """
        Create a backup of the target folder.

        Args:
            target_path: Path to the target folder to backup
            profile_name: Name of the profile (used in backup ID)

        Returns:
            backup_id (or None if target does not exist)

        Raises:
            OSError: If not enough disk space or other I/O errors
        """
        target = Path(target_path)

        # If target doesn't exist, skip silently
        if not target.exists():
            logger.warning(f"Target folder does not exist at backup time: {target_path} — skipping backup")
            return None

        backup_id = self._generate_backup_id(profile_name)
        filename = f"{backup_id}.zip"
        backup_path = BACKUPS_DIR / filename

        try:
            # Create zip file
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in target.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(target)
                        zf.write(file_path, arcname)

            # Create metadata entry
            entry = BackupEntry(
                id=backup_id,
                filename=filename,
                profile=profile_name,
                target=str(target.resolve()),
                created_at=datetime.now().isoformat(timespec="seconds"),
                run_result="pending",
                pinned=False,
                note=""
            )

            # Add to registry
            entries = self._load_registry()
            entries.append(entry)
            self._save_registry(entries)

            logger.info(f"Backup created: {backup_id} ({backup_path})")
            return backup_id

        except OSError as e:
            logger.error(f"Failed to create backup: {e}")
            raise

    def finalize_backup(self, backup_id: str, result: str):
        """
        Update backup status after run completes.

        Args:
            backup_id: ID of the backup to finalize
            result: "success" or "failed"
        """
        if result not in ("success", "failed"):
            raise ValueError(f"Invalid result: {result}. Must be 'success' or 'failed'.")

        entries = self._load_registry()
        for entry in entries:
            if entry.id == backup_id:
                entry.run_result = result
                self._save_registry(entries)
                logger.info(f"Backup finalized: {backup_id} ({result})")
                return

        raise ValueError(f"Backup not found: {backup_id}")

    def rotate_backups(self, max_backups: int = 10):
        """
        Delete oldest non-pinned backups if count exceeds max_backups.

        Args:
            max_backups: Maximum number of non-pinned backups to keep
        """
        entries = self._load_registry()
        non_pinned = [e for e in entries if not e.pinned]

        if len(non_pinned) > max_backups:
            # Sort by created_at ascending (oldest first)
            non_pinned.sort(key=lambda e: e.created_at)

            # Delete oldest entries until within limit
            to_delete = non_pinned[: len(non_pinned) - max_backups]
            for entry in to_delete:
                self.delete_backup(entry.id, force=True)  # force=True to bypass pinned check

    def list_backups(self, profile: str = None) -> list[BackupEntry]:
        """
        List all backups, optionally filtered by profile.

        Args:
            profile: Filter by profile name (None = all)

        Returns:
            List of BackupEntry, sorted by created_at descending (most recent first)
        """
        entries = self._load_registry()
        if profile:
            entries = [e for e in entries if e.profile == profile]
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries

    def get_backup(self, backup_id: str) -> BackupEntry:
        """Get a backup entry by ID."""
        entries = self._load_registry()
        for entry in entries:
            if entry.id == backup_id:
                return entry
        raise ValueError(f"Backup not found: {backup_id}")

    def restore_backup(self, backup_id: str, target_path: str = None) -> bool:
        """
        Restore a backup to the target path.

        Args:
            backup_id: ID of the backup to restore
            target_path: Override path to restore to (default: original target from backup)

        Returns:
            True if successful

        Raises:
            ValueError: If backup not found or zip is corrupted
            OSError: If extraction fails
        """
        entry = self.get_backup(backup_id)
        restore_path = Path(target_path) if target_path else Path(entry.target)

        backup_file = BACKUPS_DIR / entry.filename

        if not backup_file.exists():
            raise ValueError(f"Backup file not found: {backup_file}")

        try:
            with zipfile.ZipFile(backup_file, "r") as zf:
                zf.extractall(restore_path)
            logger.info(f"Backup restored: {backup_id} to {restore_path}")
            return True
        except zipfile.BadZipFile as e:
            raise ValueError(f"Corrupted backup file: {e}")
        except OSError as e:
            raise OSError(f"Failed to restore backup: {e}")

    def delete_backup(self, backup_id: str, force: bool = False) -> bool:
        """
        Delete a backup by ID.

        Args:
            backup_id: ID of the backup to delete
            force: If True, delete even if pinned

        Returns:
            True if deleted, False if blocked by pinned status

        Raises:
            ValueError: If backup not found
        """
        entry = self.get_backup(backup_id)

        if entry.pinned and not force:
            raise ValueError(
                f"Backup '{backup_id}' is pinned. Use 'mcru backup unpin' first or pass --force."
            )

        backup_file = BACKUPS_DIR / entry.filename
        if backup_file.exists():
            backup_file.unlink()
            logger.info(f"Backup file deleted: {backup_file}")

        entries = self._load_registry()
        entries = [e for e in entries if e.id != backup_id]
        self._save_registry(entries)

        logger.info(f"Backup deleted: {backup_id}")
        return True

    def pin_backup(self, backup_id: str, note: str = ""):
        """
        Pin a backup to prevent automatic deletion.

        Args:
            backup_id: ID of the backup to pin
            note: Optional note/label for the backup
        """
        entries = self._load_registry()
        for entry in entries:
            if entry.id == backup_id:
                entry.pinned = True
                if note:
                    entry.note = note
                self._save_registry(entries)
                logger.info(f"Backup pinned: {backup_id}")
                return

        raise ValueError(f"Backup not found: {backup_id}")

    def unpin_backup(self, backup_id: str):
        """Unpin a backup to allow automatic deletion."""
        entries = self._load_registry()
        for entry in entries:
            if entry.id == backup_id:
                entry.pinned = False
                self._save_registry(entries)
                logger.info(f"Backup unpinned: {backup_id}")
                return

        raise ValueError(f"Backup not found: {backup_id}")

    def set_note(self, backup_id: str, note: str):
        """Set or update the note on a backup."""
        entries = self._load_registry()
        for entry in entries:
            if entry.id == backup_id:
                entry.note = note
                self._save_registry(entries)
                logger.info(f"Backup note updated: {backup_id}")
                return

        raise ValueError(f"Backup not found: {backup_id}")

    def prune_backups(self, keep: int = None, include_pinned: bool = False) -> int:
        """
        Delete old backups, excluding pinned (unless include_pinned=True).

        Args:
            keep: Number of backups to keep (default: delete all)
            include_pinned: If True, include pinned backups in deletion

        Returns:
            Number of backups deleted
        """
        entries = self._load_registry()

        # Filter backups based on pinned status
        if include_pinned:
            candidates = entries
        else:
            candidates = [e for e in entries if not e.pinned]

        # If keep is specified, keep the most recent ones
        if keep is not None:
            candidates.sort(key=lambda e: e.created_at, reverse=True)
            to_delete = candidates[keep:]
        else:
            to_delete = candidates

        deleted_count = 0
        for entry in to_delete:
            backup_file = BACKUPS_DIR / entry.filename
            if backup_file.exists():
                backup_file.unlink()
            entries = [e for e in entries if e.id != entry.id]
            deleted_count += 1

        self._save_registry(entries)
        logger.info(f"Pruned {deleted_count} backups")
        return deleted_count

    def view_backup_contents(self, backup_id: str) -> list[tuple[str, int]]:
        """
        List files in a backup without extracting.

        Returns:
            List of tuples (filepath, size in bytes), sorted by filepath
        """
        entry = self.get_backup(backup_id)
        backup_file = BACKUPS_DIR / entry.filename

        if not backup_file.exists():
            raise ValueError(f"Backup file not found: {backup_file}")

        try:
            contents = []
            with zipfile.ZipFile(backup_file, "r") as zf:
                for info in zf.infolist():
                    if not info.is_dir():
                        contents.append((info.filename, info.file_size))
            contents.sort()
            return contents
        except zipfile.BadZipFile as e:
            raise ValueError(f"Corrupted backup file: {e}")
