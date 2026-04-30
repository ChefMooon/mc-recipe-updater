"""Tests for sync progress and cancellation hooks."""

import threading

import pytest

from syncer import MCRU, SyncCancelled


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