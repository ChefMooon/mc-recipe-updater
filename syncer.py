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
import os
import shutil
import tempfile
from threading import Event
from typing import Callable
from pathlib import Path
from registry import get_parser


class SyncCancelled(Exception):
    """Raised when a sync run is cancelled between file operations."""

    def __init__(self, message: str = "Sync cancelled.", results: dict | None = None):
        super().__init__(message)
        self.results = _copy_results(results or _empty_results())


_CAPTURE_FILE_STATE = object()


def _empty_results() -> dict:
    return {
        "added": [], "updated": [], "removed": [], "unchanged": [],
        "dirs_added": [], "dirs_removed": [], "errors": [],
    }


def _copy_results(results: dict) -> dict:
    return {key: list(results.get(key, [])) for key in _empty_results()}


class _SyncTransaction:
    """Journal filesystem changes so a failed run can reverse them."""

    def __init__(self, target: Path):
        self.target = target
        self.workspace = None
        self.journal = []
        self.files_before = {}
        self.dirs_before = {}

    def _ensure_workspace(self):
        if self.workspace is not None:
            return

        parent = self.target if self.target.is_dir() else self.target.parent
        while not parent.exists():
            parent = parent.parent
        self.workspace = Path(tempfile.mkdtemp(prefix=".mcru-transaction-", dir=parent))

    def _track_file(self, path: Path, original=_CAPTURE_FILE_STATE):
        if path in self.files_before:
            return
        if original is _CAPTURE_FILE_STATE:
            original = hashlib.md5(path.read_bytes()).hexdigest() if path.is_file() else None
        self.files_before[path] = original

    def _track_dir(self, path: Path, existed: bool):
        self.dirs_before.setdefault(path, existed)

    def _backup_path(self) -> Path:
        return self.workspace / f"file-{len(self.journal):06d}"

    def ensure_directory(self, path: Path):
        self._ensure_workspace()
        missing = []
        current = path
        while not current.exists():
            missing.append(current)
            if current.parent == current:
                raise OSError(f"No existing parent directory for {path}")
            current = current.parent

        for directory in reversed(missing):
            directory.mkdir()
            self._track_dir(directory, False)
            self.journal.append(("remove_dir", directory))

    def copy_file(self, source: Path, destination: Path, is_update: bool):
        self._ensure_workspace()
        self.ensure_directory(destination.parent)
        backup = None
        if is_update:
            self._track_file(destination)
            backup = self._backup_path()
            shutil.copy2(destination, backup)
        else:
            self._track_file(destination, None)

        descriptor, stage_name = tempfile.mkstemp(
            prefix=f".{destination.name}.mcru-",
            suffix=".tmp",
            dir=destination.parent,
        )
        os.close(descriptor)
        staged = Path(stage_name)
        self._track_file(staged, None)
        self.journal.append(("remove_file", staged))
        shutil.copy2(source, staged)

        if is_update:
            self.journal.append(("restore_file", destination, backup))
        else:
            self.journal.append(("remove_file", destination))
        os.replace(staged, destination)

    def remove_file(self, path: Path):
        self._ensure_workspace()
        self._track_file(path)
        backup = self._backup_path()
        shutil.copy2(path, backup)
        self.journal.append(("restore_file", path, backup))
        path.unlink(missing_ok=True)

    def remove_directory(self, path: Path):
        self._ensure_workspace()
        metadata = path.stat()
        self._track_dir(path, True)
        self.journal.append((
            "restore_dir", path, metadata.st_mode, metadata.st_atime, metadata.st_mtime,
        ))
        path.rmdir()

    def rollback(self):
        errors = []
        for entry in reversed(self.journal):
            action, path, *details = entry
            try:
                if action == "remove_file":
                    path.unlink(missing_ok=True)
                elif action == "restore_file":
                    backup, = details
                    if not path.exists():
                        path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, path)
                elif action == "remove_dir":
                    if path.exists():
                        path.rmdir()
                elif action == "restore_dir":
                    mode, atime, mtime = details
                    if not path.exists():
                        path.mkdir()
                        os.chmod(path, mode)
                        os.utime(path, (atime, mtime))
            except Exception as error:
                errors.append((self._display_path(path), str(error)))
        return errors

    def net_changes(self):
        changes = {key: [] for key in ("added", "updated", "removed", "dirs_added", "dirs_removed")}
        errors = []

        for path, original in self.files_before.items():
            try:
                exists = path.is_file()
                current = hashlib.md5(path.read_bytes()).hexdigest() if exists else None
            except Exception as error:
                errors.append((self._display_path(path), f"Could not inspect retained file: {error}"))
                continue
            rel_path = self._display_path(path)
            if original is None and exists:
                changes["added"].append(rel_path)
            elif original is not None and not exists:
                changes["removed"].append(rel_path)
            elif original is not None and current != original:
                changes["updated"].append(rel_path)

        for path, existed in self.dirs_before.items():
            try:
                exists = path.is_dir()
            except Exception as error:
                errors.append((self._display_path(path), f"Could not inspect retained directory: {error}"))
                continue
            rel_path = self._display_path(path)
            if rel_path is None:
                continue
            if not existed and exists:
                changes["dirs_added"].append(rel_path)
            elif existed and not exists:
                changes["dirs_removed"].append(rel_path)
        return changes, errors

    def _display_path(self, path: Path):
        try:
            relative = path.relative_to(self.target)
        except ValueError:
            return str(path)
        if relative == Path("."):
            return None
        return relative.as_posix()

    def cleanup(self):
        if self.workspace is not None:
            shutil.rmtree(self.workspace)
            self.workspace = None


class MCRU:
    # Files at the root of the target that are never removed, regardless of source contents.
    # CHANGELOG.md is tool-managed and must not be deleted between runs.
    TARGET_PROTECTED_FILES = {"CHANGELOG.md"}

    def __init__(
        self,
        config: dict,
        dry_run: bool = False,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_event: Event | None = None,
    ):
        self.source = Path(config["source"])
        self.target = Path(config["target"])
        self.parsers = config.get("parsers", [])
        self.mapping = config.get("mapping")
        self.dry_run = dry_run
        self.progress_callback = progress_callback or (lambda current, total, operation: None)
        self.cancel_event = cancel_event
        self._partial_results = _empty_results()

        if not self.source.exists():
            raise FileNotFoundError(f"Source folder not found: {self.source}")

    def run(self) -> dict:
        """Run the full compare + sync pipeline. Returns a results dict."""
        self._partial_results = _empty_results()
        self._check_cancel()
        if self.mapping:
            return self._run_with_mapping()

        return self._run_default()

    def _progress(self, current: int, total: int, operation: str) -> None:
        self.progress_callback(current, total, operation)

    def _check_cancel(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise SyncCancelled("Sync cancelled.", self._partial_results)

    def _apply_step(self, transaction, path, current, total, operation, mutation) -> bool:
        self._check_cancel()
        self._progress(current, total, operation)
        return self._apply_mutation(path, mutation)

    def _apply_mutation(self, path, mutation) -> bool:
        if self.dry_run:
            return True
        try:
            mutation()
            return True
        except Exception as error:
            self._partial_results["errors"].append((path, str(error)))
            return False

    def _finish_transaction(self, transaction, failed: bool, results: dict) -> dict:
        if transaction is None:
            return {"rollback_complete": None, "recovery_path": None, "rollback_errors": []}

        if not failed:
            recovery_path = None
            try:
                transaction.cleanup()
            except Exception as error:
                recovery_path = str(transaction.workspace)
                results["errors"].append((str(transaction.workspace), f"Could not clean up transaction workspace: {error}"))
            return {"rollback_complete": None, "recovery_path": recovery_path, "rollback_errors": []}

        rollback_errors = transaction.rollback()
        changes, inspection_errors = transaction.net_changes()
        rollback_errors.extend(inspection_errors)
        for key in ("added", "updated", "removed", "dirs_added", "dirs_removed"):
            results[key][:] = changes[key]

        complete = not rollback_errors
        recovery_path = None
        if complete:
            try:
                transaction.cleanup()
            except Exception as error:
                recovery_path = str(transaction.workspace)
                results["errors"].append((str(transaction.workspace), f"Could not clean up transaction workspace: {error}"))
        else:
            recovery_path = str(transaction.workspace)
        for path, message in rollback_errors:
            results["errors"].append((path, f"Rollback failed: {message}"))
        return {
            "rollback_complete": complete,
            "recovery_path": recovery_path,
            "rollback_errors": rollback_errors,
        }

    def _run_default(self) -> dict:
        """Run legacy sync behavior with direct source/target path mirroring."""
        self._progress(0, 0, "Scanning source")
        source_files = self._scan(self.source)
        self._check_cancel()
        self._progress(0, 0, "Scanning target")
        target_files = self._scan(self.target)
        self._check_cancel()

        to_add = []       # in source, missing from target
        to_update = []    # in both, but content differs
        to_remove = []    # in target, not in source
        unchanged = self._partial_results["unchanged"]

        # Compare source → target
        total_source = len(source_files)
        for index, (rel_path, src_info) in enumerate(source_files.items(), 1):
            self._check_cancel()
            self._progress(index, total_source, "Comparing files")
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
        total_target = len(target_files)
        for index, rel_path in enumerate(target_files, 1):
            self._check_cancel()
            self._progress(index, total_target, "Finding removals")
            if rel_path not in source_files and rel_path not in self.TARGET_PROTECTED_FILES:
                to_remove.append(rel_path)

        transaction = None if self.dry_run else _SyncTransaction(self.target)
        applied_add = self._partial_results["added"]
        applied_update = self._partial_results["updated"]
        applied_remove = self._partial_results["removed"]
        dirs_added = self._partial_results["dirs_added"]
        dirs_removed = self._partial_results["dirs_removed"]
        failed = False

        try:
            for index, rel_path in enumerate(to_add, 1):
                if not self._apply_step(
                    transaction, rel_path, index, len(to_add), "Adding files",
                    lambda rel=rel_path: transaction.copy_file(
                        self.source / rel, self.target / rel, False,
                    ),
                ):
                    failed = True
                    break
                applied_add.append(rel_path)

            if not failed:
                for index, rel_path in enumerate(to_update, 1):
                    if not self._apply_step(
                        transaction, rel_path, index, len(to_update), "Updating files",
                        lambda rel=rel_path: transaction.copy_file(
                            self.source / rel, self.target / rel, True,
                        ),
                    ):
                        failed = True
                        break
                    applied_update.append(rel_path)

            if not failed:
                for index, rel_path in enumerate(to_remove, 1):
                    if not self._apply_step(
                        transaction, rel_path, index, len(to_remove), "Removing files",
                        lambda rel=rel_path: transaction.remove_file(self.target / rel),
                    ):
                        failed = True
                        break
                    applied_remove.append(rel_path)

            if not failed:
                source_dirs = self._scan_all_dirs(self.source)
                self._check_cancel()

                for index, rel_dir in enumerate(sorted(source_dirs), 1):
                    target_dir_path = self.target / rel_dir
                    if not target_dir_path.exists():
                        if not self._apply_step(
                            transaction, rel_dir + "/", index, len(source_dirs), "Adding directories",
                            lambda path=target_dir_path: transaction.ensure_directory(path),
                        ):
                            failed = True
                            break
                        dirs_added.append(rel_dir)
                    else:
                        self._check_cancel()
                        self._progress(index, len(source_dirs), "Adding directories")

            if not failed:
                to_remove_set = set(to_remove)
                target_dirs = sorted(self._scan_target_dirs(transaction), reverse=True)

                for index, rel_dir in enumerate(target_dirs, 1):
                    self._check_cancel()
                    self._progress(index, len(target_dirs), "Removing directories")
                    if rel_dir in source_dirs:
                        continue
                    target_dir_path = self.target / rel_dir
                    if not target_dir_path.exists():
                        continue
                    if self.dry_run:
                        files_inside = [
                            item.relative_to(self.target).as_posix()
                            for item in target_dir_path.rglob("*") if item.is_file()
                        ]
                        if not files_inside or all(path in to_remove_set for path in files_inside):
                            dirs_removed.append(rel_dir)
                    elif not any(target_dir_path.iterdir()):
                        if not self._apply_mutation(
                            rel_dir + "/",
                            lambda path=target_dir_path: transaction.remove_directory(path),
                        ):
                            failed = True
                            break
                        dirs_removed.append(rel_dir)

            if not failed:
                self._check_cancel()
            self._progress(1, 1, "Complete")
        except SyncCancelled:
            if transaction is not None:
                try:
                    transaction.cleanup()
                except OSError:
                    pass
            raise

        results = {
            "added": applied_add,
            "updated": applied_update,
            "removed": applied_remove,
            "unchanged": unchanged,
            "dirs_added": dirs_added,
            "dirs_removed": dirs_removed,
            "errors": self._partial_results["errors"],
        }
        results.update(self._finish_transaction(transaction, failed, results))
        return results

    def _run_with_mapping(self) -> dict:
        """Run sync behavior based on source->target mapping categories."""
        self._progress(0, 0, "Building mapping")
        source_to_target = self._build_source_target_map()
        target_protect_globs = self.mapping.get("target_protect_globs", [])
        self._check_cancel()
        self._progress(0, 0, "Scanning target")
        target_files = self._scan(self.target)
        self._check_cancel()

        to_add = []
        to_update = []
        to_remove = []
        unchanged = self._partial_results["unchanged"]

        total_mapped = len(source_to_target)
        for index, (target_rel, source_rel) in enumerate(source_to_target.items(), 1):
            self._check_cancel()
            self._progress(index, total_mapped, "Comparing mapped files")
            if target_rel not in target_files:
                to_add.append(target_rel)
            else:
                src_hash = self._hash_file(self.source / source_rel)
                tgt_hash = self._hash_file(self.target / target_rel)
                if src_hash != tgt_hash:
                    to_update.append(target_rel)
                else:
                    unchanged.append(target_rel)

        total_target = len(target_files)
        for index, rel_path in enumerate(target_files, 1):
            self._check_cancel()
            self._progress(index, total_target, "Finding removals")
            if (
                rel_path not in source_to_target
                and rel_path not in self.TARGET_PROTECTED_FILES
                and not self._matches_globs(Path(rel_path), target_protect_globs)
            ):
                to_remove.append(rel_path)

        transaction = None if self.dry_run else _SyncTransaction(self.target)
        applied_add = self._partial_results["added"]
        applied_update = self._partial_results["updated"]
        applied_remove = self._partial_results["removed"]
        failed = False

        try:
            for index, target_rel in enumerate(to_add, 1):
                source_rel = source_to_target[target_rel]
                if not self._apply_step(
                    transaction, target_rel, index, len(to_add), "Adding files",
                    lambda source=source_rel, target=target_rel: transaction.copy_file(
                        self.source / source, self.target / target, False,
                    ),
                ):
                    failed = True
                    break
                applied_add.append(target_rel)

            if not failed:
                for index, target_rel in enumerate(to_update, 1):
                    source_rel = source_to_target[target_rel]
                    if not self._apply_step(
                        transaction, target_rel, index, len(to_update), "Updating files",
                        lambda source=source_rel, target=target_rel: transaction.copy_file(
                            self.source / source, self.target / target, True,
                        ),
                    ):
                        failed = True
                        break
                    applied_update.append(target_rel)

            if not failed:
                for index, target_rel in enumerate(to_remove, 1):
                    if not self._apply_step(
                        transaction, target_rel, index, len(to_remove), "Removing files",
                        lambda target=target_rel: transaction.remove_file(self.target / target),
                    ):
                        failed = True
                        break
                    applied_remove.append(target_rel)

            if not failed:
                self._check_cancel()
            self._progress(1, 1, "Complete")
        except SyncCancelled:
            if transaction is not None:
                try:
                    transaction.cleanup()
                except OSError:
                    pass
            raise

        results = {
            "added": applied_add,
            "updated": applied_update,
            "removed": applied_remove,
            "unchanged": unchanged,
            "dirs_added": self._partial_results["dirs_added"],
            "dirs_removed": self._partial_results["dirs_removed"],
            "errors": self._partial_results["errors"],
        }
        results.update(self._finish_transaction(transaction, failed, results))
        return results

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

    def _scan_target_dirs(self, transaction) -> set:
        result = self._scan_all_dirs(self.target)
        if transaction is not None and transaction.workspace is not None:
            try:
                workspace_rel = transaction.workspace.relative_to(self.target).as_posix()
            except ValueError:
                return result
            result = {
                rel_path for rel_path in result
                if rel_path != workspace_rel and not rel_path.startswith(workspace_rel + "/")
            }
        return result

    def _build_source_target_map(self) -> dict[str, str]:
        source_roots = self.mapping.get("source_roots", {})
        target_roots = self.mapping.get("target_roots", {})
        category_map = self.mapping.get("category_map", {})
        omit_globs = self.mapping.get("omit_globs", [])
        target_protect_globs = self.mapping.get("target_protect_globs", [])

        source_to_target = {}

        for source_category, target_category in category_map.items():
            self._check_cancel()
            source_dirs = self._resolve_source_dirs(source_category, source_roots)
            target_root = target_roots.get(target_category)
            if target_root is None:
                raise ValueError(
                    f"Mapping target category '{target_category}' has no target root."
                )

            for source_dir in source_dirs:
                for source_file in source_dir.rglob("*"):
                    self._check_cancel()
                    if not source_file.is_file():
                        continue

                    source_rel_to_root = source_file.relative_to(self.source)
                    if self._is_omitted(source_rel_to_root, omit_globs):
                        continue

                    relative_inside_category = source_file.relative_to(source_dir)
                    target_rel = (Path(target_root) / relative_inside_category).as_posix()
                    if self._matches_globs(Path(target_rel), target_protect_globs):
                        continue

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
        return self._matches_globs(source_rel_path, patterns)

    def _matches_globs(self, rel_path: Path, patterns: list[str]) -> bool:
        if not patterns:
            return False

        rel = rel_path.as_posix()
        parts = rel_path.parts
        for pattern in patterns:
            if fnmatch.fnmatch(rel, pattern):
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
