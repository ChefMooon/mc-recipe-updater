"""
Tests for the backup module and related functionality.

Tests cover:
- BackupManager.create_backup
- BackupManager.finalize_backup
- BackupManager.rotate_backups
- BackupManager.restore_backup
- BackupManager.delete_backup
- Backup CLI commands
- Backup integration with run command
"""

import pytest
import json
import tempfile
import zipfile
from click.testing import CliRunner
from itertools import count
from pathlib import Path
from datetime import datetime
import cli as cli_module
import backup as backup_module
from backup import BackupManager, BackupEntry


@pytest.fixture
def temp_target_dir():
    """Create a temporary target directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "target"
        target.mkdir()
        
        # Create some test files
        (target / "file1.txt").write_text("content1")
        (target / "file2.txt").write_text("content2")
        
        subdir = target / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested content")
        
        yield target


@pytest.fixture
def backup_manager(monkeypatch, tmp_path):
    """Create a BackupManager with temporary backup directory."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    registry_file = tmp_path / "backups.json"
    registry_file.write_text("[]")
    
    # Monkeypatch the backup paths
    monkeypatch.setattr("backup.BACKUPS_DIR", backup_dir)
    monkeypatch.setattr("backup.BACKUPS_REGISTRY", registry_file)

    backup_id_count = count()
    generate_backup_id = BackupManager._generate_backup_id

    def generate_unique_backup_id(manager, profile_name):
        return f"{generate_backup_id(manager, profile_name)}_{next(backup_id_count)}"

    monkeypatch.setattr(BackupManager, "_generate_backup_id", generate_unique_backup_id)
    
    return BackupManager()


class TestBackupManagerCreateBackup:
    """Tests for BackupManager.create_backup"""

    def test_create_backup_creates_zip(self, backup_manager, temp_target_dir):
        """create_backup should create a zip file."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        
        assert backup_id is not None
        assert backup_id.startswith("backup_test-profile_")
        
        # Check that zip file exists
        backup_file = backup_module.BACKUPS_DIR / f"{backup_id}.zip"
        assert backup_file.exists()
        assert backup_file.suffix == ".zip"

    def test_create_backup_contains_files(self, backup_manager, temp_target_dir):
        """Backup zip should contain all files from target."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        
        backup_file = backup_module.BACKUPS_DIR / f"{backup_id}.zip"
        with zipfile.ZipFile(backup_file, "r") as zf:
            names = zf.namelist()
            assert "file1.txt" in names
            assert "file2.txt" in names
            assert "subdir/nested.txt" in names

    def test_create_backup_records_metadata(self, backup_manager, temp_target_dir):
        """create_backup should record metadata in backups.json."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        
        # Load registry
        registry_content = backup_module.BACKUPS_REGISTRY.read_text()
        entries = json.loads(registry_content)
        
        assert len(entries) == 1
        assert entries[0]["id"] == backup_id
        assert entries[0]["profile"] == "test-profile"
        assert entries[0]["run_result"] == "pending"
        assert entries[0]["pinned"] is False

    def test_create_backup_nonexistent_target_returns_none(self, backup_manager):
        """create_backup should return None if target doesn't exist."""
        result = backup_manager.create_backup("/nonexistent/path", "test")
        assert result is None


class TestBackupManagerRotation:
    """Tests for BackupManager.rotate_backups"""

    def test_rotate_deletes_oldest_when_over_limit(self, backup_manager, temp_target_dir):
        """rotate_backups should delete oldest non-pinned backups when over limit."""
        # Create multiple backups
        backup_ids = []
        for i in range(12):
            backup_id = backup_manager.create_backup(str(temp_target_dir), f"profile-{i % 2}")
            backup_ids.append(backup_id)
        
        # Rotate with limit of 10
        backup_manager.rotate_backups(max_backups=10)
        
        # Check that only 10 remain
        entries = backup_manager.list_backups()
        assert len(entries) == 10

    def test_rotate_preserves_pinned(self, backup_manager, temp_target_dir):
        """rotate_backups should not delete pinned backups."""
        # Create backups
        backup_ids = []
        for i in range(12):
            backup_id = backup_manager.create_backup(str(temp_target_dir), f"profile")
            backup_ids.append(backup_id)
        
        # Pin the oldest backup
        entries = sorted(backup_manager.list_backups(), key=lambda e: e.created_at)
        backup_manager.pin_backup(entries[0].id)
        
        # Rotate
        backup_manager.rotate_backups(max_backups=10)
        
        # Check that pinned backup still exists
        remaining = backup_manager.list_backups()
        pinned_ids = [e.id for e in remaining if e.pinned]
        assert entries[0].id in pinned_ids


class TestBackupManagerRestore:
    """Tests for BackupManager.restore_backup"""

    def test_restore_backup_extracts_files(self, backup_manager, temp_target_dir):
        """restore_backup should extract files to target."""
        # Create backup
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        
        # Create new restore directory
        with tempfile.TemporaryDirectory() as restore_dir:
            restore_path = Path(restore_dir) / "restored"
            restore_path.mkdir()
            
            # Restore
            backup_manager.restore_backup(backup_id, target_path=str(restore_path))
            
            # Check files exist
            assert (restore_path / "file1.txt").exists()
            assert (restore_path / "file2.txt").exists()
            assert (restore_path / "subdir" / "nested.txt").exists()


class TestBackupManagerDelete:
    """Tests for BackupManager.delete_backup"""

    def test_delete_backup_removes_file(self, backup_manager, temp_target_dir):
        """delete_backup should remove the backup file."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        backup_file = backup_module.BACKUPS_DIR / f"{backup_id}.zip"
        assert backup_file.exists()
        
        # Delete
        backup_manager.delete_backup(backup_id)
        
        # Check file is gone
        assert not backup_file.exists()

    def test_delete_pinned_without_force_raises(self, backup_manager, temp_target_dir):
        """delete_backup should raise error if backup is pinned and force=False."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        backup_manager.pin_backup(backup_id)
        
        # Try to delete without force
        with pytest.raises(ValueError, match="is pinned"):
            backup_manager.delete_backup(backup_id, force=False)

    def test_delete_pinned_with_force_succeeds(self, backup_manager, temp_target_dir):
        """delete_backup should delete if force=True even if pinned."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        backup_manager.pin_backup(backup_id)
        
        # Delete with force
        result = backup_manager.delete_backup(backup_id, force=True)
        
        assert result is True
        backup_file = backup_module.BACKUPS_DIR / f"{backup_id}.zip"
        assert not backup_file.exists()


class TestBackupManagerPin:
    """Tests for BackupManager pin/unpin"""

    def test_pin_backup_sets_pinned_flag(self, backup_manager, temp_target_dir):
        """pin_backup should set pinned flag to True."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        
        backup_manager.pin_backup(backup_id)
        
        entry = backup_manager.get_backup(backup_id)
        assert entry.pinned is True

    def test_pin_with_note(self, backup_manager, temp_target_dir):
        """pin_backup should set note if provided."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        
        backup_manager.pin_backup(backup_id, note="important backup")
        
        entry = backup_manager.get_backup(backup_id)
        assert entry.note == "important backup"

    def test_unpin_backup_clears_pinned_flag(self, backup_manager, temp_target_dir):
        """unpin_backup should set pinned flag to False."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        backup_manager.pin_backup(backup_id)
        
        backup_manager.unpin_backup(backup_id)
        
        entry = backup_manager.get_backup(backup_id)
        assert entry.pinned is False


class TestBackupManagerView:
    """Tests for BackupManager.view_backup_contents"""

    def test_view_backup_contents_lists_files(self, backup_manager, temp_target_dir):
        """view_backup_contents should return list of files with sizes."""
        backup_id = backup_manager.create_backup(str(temp_target_dir), "test-profile")
        
        contents = backup_manager.view_backup_contents(backup_id)
        
        assert len(contents) == 3
        file_names = [name for name, _ in contents]
        assert "file1.txt" in file_names
        assert "file2.txt" in file_names


def test_prune_aborts_without_deleting_when_preview_candidates_changed(backup_manager, temp_target_dir):
    backup_ids = [
        backup_manager.create_backup(str(temp_target_dir), f"profile-{index}")
        for index in range(3)
    ]

    with pytest.raises(RuntimeError, match="changed after preview"):
        backup_manager.prune_backups(keep=1, expected_ids={backup_ids[0]})

    assert {entry.id for entry in backup_manager.list_backups()} == set(backup_ids)


def test_prune_deletes_only_the_confirmed_candidate_ids(backup_manager, temp_target_dir):
    for index in range(3):
        backup_manager.create_backup(str(temp_target_dir), f"profile-{index}")
    candidates = backup_manager.list_backups()
    expected_ids = {entry.id for entry in candidates[1:]}

    assert backup_manager.prune_backups(keep=1, expected_ids=expected_ids) == len(expected_ids)
    assert {entry.id for entry in backup_manager.list_backups()} == {candidates[0].id}


class TestBackupCLIIntegration:
    """Tests for backup CLI command integration"""

    def _install_path_preflight_config(self, monkeypatch, source, target, suite=None):
        backup_calls = []

        class _ConfigManager:
            def get_profile(self, name):
                if name == "profile":
                    return {
                        "name": name,
                        "source": str(source),
                        "target": str(target),
                        "parsers": [],
                    }
                return None

            def get_suite(self, name):
                return suite if name == "suite" else None

            def get_mapping_preset(self, _name):
                raise AssertionError("mapping lookup was not expected")

        class _GlobalConfig:
            def get(self, key, default=None):
                return {"backup.enabled": True, "backup.max_backups": 0}.get(key, default)

        class _BackupManager:
            def create_backup(self, *_args, **_kwargs):
                backup_calls.append("created")
                return "backup-id"

        monkeypatch.setattr(cli_module, "ConfigManager", _ConfigManager)
        monkeypatch.setattr(cli_module, "GlobalConfig", _GlobalConfig)
        monkeypatch.setattr(cli_module, "BackupManager", _BackupManager)
        return backup_calls

    def _install_failed_sync(self, monkeypatch, backup_manager, source, target, rollback_complete):
        outcome_calls = []

        class _ConfigManager:
            def get_profile(self, name):
                if name == "profile":
                    return {"name": name, "source": str(source), "target": str(target), "parsers": []}
                return None

            def get_suite(self, name):
                return {"name": name, "profiles": ["profile"]} if name == "suite" else None

            def get_mapping_preset(self, _name):
                raise AssertionError("mapping lookup was not expected")

        class _GlobalConfig:
            def get(self, key, default=None):
                return {"backup.enabled": True, "backup.max_backups": 0}.get(key, default)

        class _MCRU:
            def __init__(self, *_args, **_kwargs):
                pass

            def run(self):
                return {
                    "added": [],
                    "updated": [],
                    "removed": [],
                    "unchanged": [],
                    "dirs_added": [],
                    "dirs_removed": [],
                    "errors": [("bad.json", "injected mutation failure")],
                    "rollback_complete": rollback_complete,
                    "recovery_path": "transaction-recovery" if rollback_complete is False else None,
                    "rollback_errors": [],
                }

        class _Reporter:
            def __init__(self, _name, _config, _results, dry_run=False, outcome="success"):
                outcome_calls.append(outcome)

            def print_summary(self):
                pass

            def save_report(self):
                return "profile-report.txt"

        class _SuiteReporter:
            def __init__(self, _name, _runs, dry_run=False, outcome="success"):
                outcome_calls.append(outcome)

            def print_summary(self):
                pass

            def save_report(self):
                return "suite-report.txt"

        monkeypatch.setattr(cli_module, "ConfigManager", _ConfigManager)
        monkeypatch.setattr(cli_module, "GlobalConfig", _GlobalConfig)
        monkeypatch.setattr(cli_module, "BackupManager", lambda: backup_manager)
        monkeypatch.setattr(cli_module, "MCRU", _MCRU)
        monkeypatch.setattr(cli_module, "Reporter", _Reporter)
        monkeypatch.setattr(cli_module, "SuiteReporter", _SuiteReporter)
        return outcome_calls

    @staticmethod
    def _make_run_dirs(tmp_path):
        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()
        target.mkdir()
        (target / "before.txt").write_text("before")
        return source, target

    def test_run_with_no_backup_flag_skips_backup(self, monkeypatch):
        """mcru run --no-backup should skip backup creation."""
        # This would be tested with Click's CliRunner
        # Placeholder for full integration test
        pass

    def test_run_with_backup_flag_forces_backup(self, monkeypatch):
        """mcru run --backup should create backup even if globally disabled."""
        # This would be tested with Click's CliRunner
        # Placeholder for full integration test
        pass

    def test_profile_mutation_failure_marks_backup_failed_and_skips_rotation(
        self, monkeypatch, tmp_path, backup_manager
    ):
        source, target = self._make_run_dirs(tmp_path)
        outcomes = self._install_failed_sync(
            monkeypatch, backup_manager, source, target, rollback_complete=True
        )

        result = CliRunner().invoke(cli_module.cli, ["run", "profile", "--no-report"])

        assert result.exit_code == 1
        assert outcomes == ["failed"]
        backups = backup_manager.list_backups(profile="profile")
        assert len(backups) == 1
        assert backups[0].run_result == "failed"

    def test_suite_mutation_failure_marks_backup_failed_and_reports_partial(
        self, monkeypatch, tmp_path, backup_manager
    ):
        source, target = self._make_run_dirs(tmp_path)
        outcomes = self._install_failed_sync(
            monkeypatch, backup_manager, source, target, rollback_complete=False
        )

        result = CliRunner().invoke(cli_module.cli, ["run", "suite", "--no-report"])

        assert result.exit_code == 1
        assert outcomes == ["partial"]
        backups = backup_manager.list_backups(profile="profile")
        assert len(backups) == 1
        assert backups[0].run_result == "failed"

    def test_quick_mutation_failure_is_not_reported_as_success(self, monkeypatch, tmp_path, backup_manager):
        source, target = self._make_run_dirs(tmp_path)
        outcomes = self._install_failed_sync(
            monkeypatch, backup_manager, source, target, rollback_complete=True
        )

        result = CliRunner().invoke(cli_module.cli, ["quick", str(source), str(target)])

        assert result.exit_code == 1
        assert outcomes == ["failed"]

    @pytest.mark.parametrize("invalid_roots", ["source_file", "target_file", "overlap"])
    def test_profile_path_preflight_fails_before_backup(
        self, monkeypatch, tmp_path, invalid_roots
    ):
        source, target = self._make_run_dirs(tmp_path)
        if invalid_roots == "source_file":
            source.rmdir()
            source.write_text("not a directory")
        elif invalid_roots == "target_file":
            (target / "before.txt").unlink()
            target.rmdir()
            target.write_text("not a directory")
        else:
            source = target / "nested-source"
            source.mkdir()
        backup_calls = self._install_path_preflight_config(
            monkeypatch, source, target
        )

        result = CliRunner().invoke(cli_module.cli, ["run", "profile"])

        assert result.exit_code == 1
        assert "Invalid sync paths" in result.output
        assert backup_calls == []
        if target.is_dir():
            assert (target / "before.txt").read_text() == "before"

    def test_suite_skips_unsafe_profile_with_reason_before_backup(self, monkeypatch, tmp_path):
        source, target = self._make_run_dirs(tmp_path)
        source = target / "nested-source"
        source.mkdir()
        backup_calls = self._install_path_preflight_config(
            monkeypatch, source, target, suite={"name": "suite", "profiles": ["profile"]}
        )

        result = CliRunner().invoke(cli_module.cli, ["run", "suite", "--no-report"])

        assert "Profile 'profile'" in result.output
        assert "overlap" in result.output
        assert "skipping" in result.output
        assert backup_calls == []
        assert (target / "before.txt").read_text() == "before"

    def test_quick_path_preflight_returns_nonzero_for_non_directory(self, tmp_path):
        source = tmp_path / "source"
        source.write_text("not a directory")
        target = tmp_path / "target"
        target.mkdir()

        result = CliRunner().invoke(cli_module.cli, ["quick", str(source), str(target)])

        assert result.exit_code == 1
        assert "Invalid sync paths" in result.output
        assert str(source) in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
