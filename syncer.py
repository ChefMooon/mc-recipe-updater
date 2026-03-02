"""
Syncer - Core diff and sync engine.

Compares source vs target using MD5 hashing, then applies changes:
  - Add files that exist in source but not target
  - Remove files that exist in target but not source
  - Update files where the content differs (source is authoritative)
  - Create empty directories that exist in source but not target
  - Remove empty orphan directories in target that don't exist in source

Supports optional parsers that transform file content before hashing,
so whitespace or encoding differences don't create false positives.
"""

import hashlib
import fnmatch
import shutil
from pathlib import Path
from registry import get_parser


class MCRU:
    # Files at the root of the target that are never removed, regardless of source contents.
    # CHANGELOG.md is tool-managed and must not be deleted between runs.
    TARGET_PROTECTED_FILES = {"CHANGELOG.md"}

    def __init__(self, config: dict, dry_run: bool = False):
        self.source = Path(config["source"])
        self.target = Path(config["target"])
        self.parsers = config.get("parsers", [])
        self.mapping = config.get("mapping")
        self.dry_run = dry_run

        if not self.source.exists():
            raise FileNotFoundError(f"Source folder not found: {self.source}")

    def run(self) -> dict:
        """Run the full compare + sync pipeline. Returns a results dict."""
        if self.mapping:
            return self._run_with_mapping()

        return self._run_default()

    def _run_default(self) -> dict:
        """Run legacy sync behavior with direct source/target path mirroring."""
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
            if rel_path not in source_files and rel_path not in self.TARGET_PROTECTED_FILES:
                to_remove.append(rel_path)

        # Apply changes
        applied_add = []
        applied_update = []
        applied_remove = []
        errors = []

        for rel_path in to_add:
            try:
                if not self.dry_run:
                    self._copy(self.source / rel_path, self.target / rel_path)
                applied_add.append(rel_path)
            except Exception as e:
                errors.append((rel_path, str(e)))

        for rel_path in to_update:
            try:
                if not self.dry_run:
                    self._copy(self.source / rel_path, self.target / rel_path)
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

        # ── Directory sync ───────────────────────────────────────────
        dirs_added = []
        dirs_removed = []

        source_dirs = self._scan_all_dirs(self.source)

        # Create source directories missing from target (sorted: parents before children)
        for rel_dir in sorted(source_dirs):
            target_dir_path = self.target / rel_dir
            if not target_dir_path.exists():
                try:
                    if not self.dry_run:
                        target_dir_path.mkdir(parents=True, exist_ok=True)
                    dirs_added.append(rel_dir)
                except Exception as e:
                    errors.append((rel_dir + "/", str(e)))

        # Remove orphan target dirs not in source
        # In live mode: only remove if actually empty (deepest first so children go first)
        # In dry-run mode: flag dirs that are currently empty or would be empty after file removals
        to_remove_set = set(to_remove)
        target_dirs = sorted(self._scan_all_dirs(self.target), reverse=True)  # deepest first

        for rel_dir in target_dirs:
            if rel_dir in source_dirs:
                continue
            target_dir_path = self.target / rel_dir
            if not target_dir_path.exists():
                continue
            if self.dry_run:
                # A dir would be removable if all files inside it are scheduled for removal
                files_inside = [
                    item.relative_to(self.target).as_posix()
                    for item in target_dir_path.rglob("*") if item.is_file()
                ]
                if not files_inside or all(f in to_remove_set for f in files_inside):
                    dirs_removed.append(rel_dir)
            else:
                # Only remove if the dir is now empty (children removed first due to reverse sort)
                if not any(target_dir_path.iterdir()):
                    try:
                        target_dir_path.rmdir()
                        dirs_removed.append(rel_dir)
                    except Exception as e:
                        errors.append((rel_dir + "/", str(e)))

        return {
            "added": applied_add,
            "updated": applied_update,
            "removed": applied_remove,
            "unchanged": unchanged,
            "dirs_added": dirs_added,
            "dirs_removed": dirs_removed,
            "errors": errors,
        }

    def _run_with_mapping(self) -> dict:
        """Run sync behavior based on source->target mapping categories."""
        source_to_target = self._build_source_target_map()
        target_files = self._scan(self.target)

        to_add = []
        to_update = []
        to_remove = []
        unchanged = []

        for target_rel, source_rel in source_to_target.items():
            if target_rel not in target_files:
                to_add.append(target_rel)
            else:
                src_hash = self._hash_file(self.source / source_rel)
                tgt_hash = self._hash_file(self.target / target_rel)
                if src_hash != tgt_hash:
                    to_update.append(target_rel)
                else:
                    unchanged.append(target_rel)

        for rel_path in target_files:
            if rel_path not in source_to_target and rel_path not in self.TARGET_PROTECTED_FILES:
                to_remove.append(rel_path)

        applied_add = []
        applied_update = []
        applied_remove = []
        errors = []

        for target_rel in to_add:
            try:
                if not self.dry_run:
                    source_rel = source_to_target[target_rel]
                    self._copy(self.source / source_rel, self.target / target_rel)
                applied_add.append(target_rel)
            except Exception as e:
                errors.append((target_rel, str(e)))

        for target_rel in to_update:
            try:
                if not self.dry_run:
                    source_rel = source_to_target[target_rel]
                    self._copy(self.source / source_rel, self.target / target_rel)
                applied_update.append(target_rel)
            except Exception as e:
                errors.append((target_rel, str(e)))

        for target_rel in to_remove:
            try:
                if not self.dry_run:
                    (self.target / target_rel).unlink(missing_ok=True)
                applied_remove.append(target_rel)
            except Exception as e:
                errors.append((target_rel, str(e)))

        return {
            "added": applied_add,
            "updated": applied_update,
            "removed": applied_remove,
            "unchanged": unchanged,
            "dirs_added": [],
            "dirs_removed": [],
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
                rel = f.relative_to(folder).as_posix()
                result[rel] = f.stat()
        return result

    def _scan_all_dirs(self, folder: Path) -> set:
        """Return a set of relative dir path strings for all directories under folder."""
        result = set()
        if not folder.exists():
            return result
        for d in folder.rglob("*"):
            if d.is_dir():
                result.add(d.relative_to(folder).as_posix())
        return result

    def _copy(self, source_path: Path, target_path: Path):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    def _build_source_target_map(self) -> dict[str, str]:
        source_roots = self.mapping.get("source_roots", {})
        target_roots = self.mapping.get("target_roots", {})
        category_map = self.mapping.get("category_map", {})
        omit_globs = self.mapping.get("omit_globs", [])

        source_to_target = {}

        for source_category, target_category in category_map.items():
            source_dirs = self._resolve_source_dirs(source_category, source_roots)
            target_root = target_roots.get(target_category)
            if target_root is None:
                raise ValueError(
                    f"Mapping target category '{target_category}' has no target root."
                )

            for source_dir in source_dirs:
                for source_file in source_dir.rglob("*"):
                    if not source_file.is_file():
                        continue

                    source_rel_to_root = source_file.relative_to(self.source)
                    if self._is_omitted(source_rel_to_root, omit_globs):
                        continue

                    relative_inside_category = source_file.relative_to(source_dir)
                    target_rel = (Path(target_root) / relative_inside_category).as_posix()
                    source_rel = source_rel_to_root.as_posix()

                    existing = source_to_target.get(target_rel)
                    if existing and existing != source_rel:
                        raise ValueError(
                            f"Mapped target path conflict: '{target_rel}' from both "
                            f"'{existing}' and '{source_rel}'."
                        )

                    source_to_target[target_rel] = source_rel

        return source_to_target

    def _resolve_source_dirs(self, category: str, source_roots: dict) -> list[Path]:
        rules = self.mapping.get("rules", {})
        entry = source_roots.get(category)
        if entry is None:
            raise ValueError(f"Mapping source category '{category}' has no source root definition.")

        if category == "forge_like" and isinstance(entry, dict):
            candidates = entry.get("candidates", [])
            # Resolve each candidate independently so we can detect a genuine
            # cross-platform conflict (forge AND neoforge both present) without
            # false-positives from projects that have multiple data namespaces
            # under a single platform (e.g. farmersdelight + frightsdelight both
            # inside forge/src/main/resources/data/*/recipes).
            per_candidate = [self._resolve_glob_dirs([c]) for c in candidates]
            active = [matches for matches in per_candidate if matches]
            if len(active) > 1 and rules.get("forge_like_conflict") == "error_if_multiple":
                all_paths = [path for group in active for path in group]
                rendered = ", ".join(str(path) for path in all_paths)
                raise ValueError(
                    "Both forge and neoforge source folders were found; expected only one. "
                    f"Found: {rendered}"
                )
            if len(active) > 1:
                # No conflict rule — fall back to first candidate's matches
                return active[0]
            if active:
                return active[0]
            return []

        if isinstance(entry, str):
            patterns = [entry]
        elif isinstance(entry, list):
            patterns = entry
        else:
            raise ValueError(f"Invalid source root format for category '{category}'.")

        return self._resolve_glob_dirs(patterns)

    def _resolve_glob_dirs(self, patterns: list[str]) -> list[Path]:
        result = []
        seen = set()
        for pattern in patterns:
            for path in self.source.glob(pattern):
                if path.is_dir():
                    normalized = str(path.resolve())
                    if normalized not in seen:
                        seen.add(normalized)
                        result.append(path)
        return result

    def _is_omitted(self, source_rel_path: Path, patterns: list[str]) -> bool:
        if not patterns:
            return False

        source_rel = source_rel_path.as_posix()
        parts = source_rel_path.parts
        for pattern in patterns:
            if fnmatch.fnmatch(source_rel, pattern):
                return True
            if any(fnmatch.fnmatch(part, pattern) for part in parts):
                return True
        return False

    def _hash_file(self, path: Path) -> str:
        """Hash a file's content, applying any configured parsers first."""
        content = path.read_bytes()

        # Apply parsers (they operate on bytes or decoded text)
        for parser_name in self.parsers:
            parser_fn = get_parser(parser_name)
            if parser_fn:
                content = parser_fn(content)

        return hashlib.md5(content).hexdigest()
