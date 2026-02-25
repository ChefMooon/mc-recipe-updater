"""
FolderSyncer - Core diff and sync engine.

Compares source vs target using MD5 hashing, then applies changes:
  - Add files that exist in source but not target
  - Remove files that exist in target but not source
  - Update files where the content differs (source is authoritative)

Supports optional parsers that transform file content before hashing,
so whitespace or encoding differences don't create false positives.
"""

import hashlib
import os
import shutil
from pathlib import Path
from registry import get_parser


class FolderSyncer:
    def __init__(self, config: dict, dry_run: bool = False):
        self.source = Path(config["source"])
        self.target = Path(config["target"])
        self.parsers = config.get("parsers", [])
        self.dry_run = dry_run

        if not self.source.exists():
            raise FileNotFoundError(f"Source folder not found: {self.source}")

    def run(self) -> dict:
        """Run the full compare + sync pipeline. Returns a results dict."""
        source_files = self._scan(self.source)
        target_files = self._scan(self.target)

        to_add = []       # in source, missing from target
        to_update = []    # in both, but content differs
        to_remove = []    # in target, not in source
        unchanged = []    # identical in both

        # Compare source → target
        for rel_path, src_info in source_files.items():
            if rel_path not in target_files:
                to_add.append(rel_path)
            else:
                src_hash = self._hash_file(self.source / rel_path)
                tgt_hash = self._hash_file(self.target / rel_path)
                if src_hash != tgt_hash:
                    to_update.append(rel_path)
                else:
                    unchanged.append(rel_path)

        # Find files only in target (should be removed)
        for rel_path in target_files:
            if rel_path not in source_files:
                to_remove.append(rel_path)

        # Apply changes
        applied_add = []
        applied_update = []
        applied_remove = []
        errors = []

        for rel_path in to_add:
            try:
                if not self.dry_run:
                    dest = self.target / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(self.source / rel_path, dest)
                applied_add.append(rel_path)
            except Exception as e:
                errors.append((rel_path, str(e)))

        for rel_path in to_update:
            try:
                if not self.dry_run:
                    dest = self.target / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(self.source / rel_path, dest)
                applied_update.append(rel_path)
            except Exception as e:
                errors.append((rel_path, str(e)))

        for rel_path in to_remove:
            try:
                if not self.dry_run:
                    (self.target / rel_path).unlink(missing_ok=True)
                applied_remove.append(rel_path)
            except Exception as e:
                errors.append((rel_path, str(e)))

        return {
            "added": applied_add,
            "updated": applied_update,
            "removed": applied_remove,
            "unchanged": unchanged,
            "errors": errors,
        }

    # ──────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────

    def _scan(self, folder: Path) -> dict:
        """Return {relative_path_str: stat} for all files under folder."""
        result = {}
        if not folder.exists():
            return result
        for f in folder.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(folder))
                result[rel] = f.stat()
        return result

    def _hash_file(self, path: Path) -> str:
        """Hash a file's content, applying any configured parsers first."""
        content = path.read_bytes()

        # Apply parsers (they operate on bytes or decoded text)
        for parser_name in self.parsers:
            parser_fn = get_parser(parser_name)
            if parser_fn:
                content = parser_fn(content)

        return hashlib.md5(content).hexdigest()
