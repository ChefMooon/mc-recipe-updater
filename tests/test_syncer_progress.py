"""Tests for sync progress and cancellation hooks."""

import threading
from pathlib import Path

import pytest

import syncer as syncer_module
from syncer import MCRU, SyncCancelled
from tui.utils import ThreadedSyncer


def test_syncer_reports_progress(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file.txt").write_text("hello")

    events = []
    syncer = MCRU(
        {"source": str(source), "target": str(target), "parsers": []},
        dry_run=True,
        progress_callback=lambda current, total, operation: events.append((current, total, operation)),
    )

    results = syncer.run()

    assert results["added"] == ["file.txt"]
    assert any(operation == "Comparing files" for _, _, operation in events)
    assert events[-1][2] == "Complete"


def test_syncer_cancels_before_work(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    cancel_event = threading.Event()
    cancel_event.set()

    syncer = MCRU(
        {"source": str(source), "target": str(target), "parsers": []},
        dry_run=True,
        cancel_event=cancel_event,
    )

    with pytest.raises(SyncCancelled):
        syncer.run()


def test_default_sync_cancellation_carries_applied_mutations(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "first.txt").write_text("first")
    (source / "second.txt").write_text("second")
    cancel_event = threading.Event()

    def cancel_after_first_add(current, _total, operation):
        if operation == "Adding files" and current == 1:
            cancel_event.set()

    syncer = MCRU(
        {"source": str(source), "target": str(target), "parsers": []},
        progress_callback=cancel_after_first_add,
        cancel_event=cancel_event,
    )

    with pytest.raises(SyncCancelled) as caught:
        syncer.run()

    assert caught.value.results["added"] == ["first.txt"]
    assert (target / "first.txt").exists()


def test_threaded_syncer_delivers_partial_results_on_cancellation(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "first.txt").write_text("first")
    (source / "second.txt").write_text("second")
    completed = []
    syncer = None

    def on_progress(current, _total, operation):
        if operation == "Adding files" and current == 1:
            syncer.cancel()

    syncer = ThreadedSyncer(
        {"source": str(source), "target": str(target), "parsers": []},
        on_progress=on_progress,
        on_complete=lambda results, error: completed.append((results, error)),
    )
    syncer.start()

    assert syncer.wait(2)
    assert len(completed) == 1
    assert isinstance(completed[0][1], SyncCancelled)
    assert completed[0][0]["added"] == ["first.txt"]


def test_default_partial_staged_write_failure_leaves_target_unchanged(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    source_file = source / "existing.bin"
    source_file.write_bytes(b"complete source content")
    (target / "existing.bin").write_bytes(b"previous target content")
    original_copy2 = syncer_module.shutil.copy2

    def write_partial_then_fail(src, dst, *args, **kwargs):
        if Path(src) == source_file:
            Path(dst).write_bytes(b"partial")
            raise OSError("injected staged write failure")
        return original_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(syncer_module.shutil, "copy2", write_partial_then_fail)

    results = MCRU({"source": str(source), "target": str(target), "parsers": []}).run()

    assert (target / "existing.bin").read_bytes() == b"previous target content"
    assert results["added"] == []
    assert results["updated"] == []
    assert results["rollback_complete"] is True
    assert results["recovery_path"] is None
    assert results["errors"][0] == ("existing.bin", "injected staged write failure")
    assert list(target.glob(".mcru-transaction-*")) == []


def test_default_partial_staged_add_failure_leaves_target_unchanged(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    source_file = source / "new.bin"
    source_file.write_bytes(b"new source content")
    (target / "existing.txt").write_text("keep")

    def write_partial_then_fail(_src, dst, *args, **kwargs):
        Path(dst).write_bytes(b"partial")
        raise OSError("injected staged add failure")

    monkeypatch.setattr(syncer_module.shutil, "copy2", write_partial_then_fail)

    results = MCRU({"source": str(source), "target": str(target), "parsers": []}).run()

    assert {path.name: path.read_bytes() for path in target.iterdir() if path.is_file()} == {
        "existing.txt": b"keep",
    }
    assert results["added"] == []
    assert results["rollback_complete"] is True
    assert results["recovery_path"] is None


def test_success_cleanup_failure_reports_recovery_workspace(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "new.txt").write_text("new")

    def fail_workspace_cleanup(*_args, **_kwargs):
        raise OSError("injected workspace cleanup failure")

    monkeypatch.setattr(syncer_module.shutil, "rmtree", fail_workspace_cleanup)

    results = MCRU({"source": str(source), "target": str(target), "parsers": []}).run()

    assert (target / "new.txt").read_text() == "new"
    assert results["rollback_complete"] is None
    assert results["recovery_path"] is not None
    assert Path(results["recovery_path"]).is_dir()
    assert "injected workspace cleanup failure" in results["errors"][-1][1]


def test_default_later_file_failure_rolls_back_add_update_and_remove(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "added.txt").write_text("new file")
    (source / "updated.txt").write_text("new version")
    (target / "updated.txt").write_text("old version")
    remove_file = target / "removed.txt"
    remove_file.write_text("keep on rollback")
    original_unlink = Path.unlink

    def fail_removal(path, *args, **kwargs):
        if path == remove_file:
            raise OSError("injected removal failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_removal)

    results = MCRU({"source": str(source), "target": str(target), "parsers": []}).run()

    assert {path.name: path.read_text() for path in target.iterdir()} == {
        "updated.txt": "old version",
        "removed.txt": "keep on rollback",
    }
    assert results["added"] == []
    assert results["updated"] == []
    assert results["removed"] == []
    assert results["rollback_complete"] is True
    assert results["rollback_errors"] == []
    assert results["errors"][0] == ("removed.txt", "injected removal failure")


def test_default_directory_create_failure_removes_prior_created_directories(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "a-created").mkdir(parents=True)
    (source / "z-fails").mkdir()
    target.mkdir()
    failed_directory = target / "z-fails"
    original_mkdir = Path.mkdir

    def fail_second_directory(path, *args, **kwargs):
        if path == failed_directory:
            raise OSError("injected directory create failure")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_second_directory)

    results = MCRU({"source": str(source), "target": str(target), "parsers": []}).run()

    assert list(target.iterdir()) == []
    assert results["dirs_added"] == []
    assert results["rollback_complete"] is True
    assert results["errors"][0] == ("z-fails/", "injected directory create failure")


def test_default_directory_remove_failure_restores_prior_file_and_directory_removals(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (target / "z-removed").mkdir()
    (target / "z-removed" / "obsolete.txt").write_text("restore me")
    failed_directory = target / "a-fails"
    failed_directory.mkdir()
    original_rmdir = Path.rmdir

    def fail_second_directory(path, *args, **kwargs):
        if path == failed_directory:
            raise OSError("injected directory remove failure")
        return original_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "rmdir", fail_second_directory)

    results = MCRU({"source": str(source), "target": str(target), "parsers": []}).run()

    assert (target / "z-removed" / "obsolete.txt").read_text() == "restore me"
    assert failed_directory.is_dir()
    assert results["removed"] == []
    assert results["dirs_removed"] == []
    assert results["rollback_complete"] is True
    assert results["errors"][0] == ("a-fails/", "injected directory remove failure")


def test_transaction_workspace_preflight_failure_does_not_mutate_target(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "new.txt").write_text("new")
    (target / "existing.txt").write_text("unchanged")

    def fail_workspace_creation(*_args, **_kwargs):
        raise OSError("injected workspace failure")

    monkeypatch.setattr(syncer_module.tempfile, "mkdtemp", fail_workspace_creation)

    results = MCRU({"source": str(source), "target": str(target), "parsers": []}).run()

    assert {path.name: path.read_text() for path in target.iterdir()} == {"existing.txt": "unchanged"}
    assert results["added"] == []
    assert results["rollback_complete"] is True
    assert results["recovery_path"] is None
    assert results["errors"][0][1] == "injected workspace failure"


def test_rollback_failure_reports_retained_changes_and_recovery_workspace(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "a-directory-fails").mkdir(parents=True)
    target.mkdir()
    source_file = source / "added.txt"
    source_file.write_text("retained add")
    failed_directory = target / "a-directory-fails"
    original_mkdir = Path.mkdir
    original_unlink = Path.unlink

    def fail_directory_create(path, *args, **kwargs):
        if path == failed_directory:
            raise OSError("injected mutation failure")
        return original_mkdir(path, *args, **kwargs)

    def fail_added_file_rollback(path, *args, **kwargs):
        if path == target / "added.txt":
            raise OSError("injected rollback failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_directory_create)
    monkeypatch.setattr(Path, "unlink", fail_added_file_rollback)

    results = MCRU({"source": str(source), "target": str(target), "parsers": []}).run()

    assert (target / "added.txt").read_text() == "retained add"
    assert results["added"] == ["added.txt"]
    assert results["rollback_complete"] is False
    assert results["recovery_path"] is not None
    assert Path(results["recovery_path"]).is_dir()
    assert results["errors"][0] == ("a-directory-fails/", "injected mutation failure")
    assert results["rollback_errors"]
    assert any("injected rollback failure" in message for _, message in results["rollback_errors"])