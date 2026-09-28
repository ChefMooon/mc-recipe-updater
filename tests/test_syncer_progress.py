"""Tests for sync progress and cancellation hooks."""

import threading

import pytest

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