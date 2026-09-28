"""Tests for mapped sync behavior."""

import threading

import pytest

from syncer import MCRU, SyncCancelled
from tui.utils import ThreadedSyncer


def test_mapping_target_protect_globs_skip_removals(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_recipe_dir = source / "fabric" / "src" / "main" / "resources" / "data" / "demo" / "recipes"
    source_recipe_dir.mkdir(parents=True)
    target.mkdir()

    (source_recipe_dir / "cake.json").write_text("new cake")
    (target / "fabric").mkdir()
    (target / "fabric" / "old.json").write_text("old")
    (target / "neoforge").mkdir()
    (target / "neoforge" / "keep.json").write_text("keep")

    syncer = MCRU(
        {
            "source": str(source),
            "target": str(target),
            "parsers": [],
            "mapping": {
                "source_roots": {
                    "fabric": ["fabric/src/main/resources/data/*/recipes"],
                },
                "target_roots": {
                    "fabric": "fabric",
                },
                "category_map": {
                    "fabric": "fabric",
                },
                "omit_globs": [],
                "target_protect_globs": ["neoforge"],
                "rules": {},
            },
        },
        dry_run=False,
    )

    results = syncer.run()

    assert "fabric/cake.json" in results["added"]
    assert "fabric/old.json" in results["removed"]
    assert "neoforge/keep.json" not in results["removed"]
    assert not (target / "fabric" / "old.json").exists()
    assert (target / "fabric" / "cake.json").read_text() == "new cake"
    assert (target / "neoforge" / "keep.json").read_text() == "keep"


def test_mapping_target_protect_globs_skip_mapped_writes(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_recipe_dir = source / "fabric" / "src" / "main" / "resources" / "data" / "demo" / "recipes"
    source_recipe_dir.mkdir(parents=True)
    (target / "fabric").mkdir(parents=True)

    (source_recipe_dir / "cake.json").write_text("new cake")
    (target / "fabric" / "cake.json").write_text("existing cake")

    syncer = MCRU(
        {
            "source": str(source),
            "target": str(target),
            "parsers": [],
            "mapping": {
                "source_roots": {
                    "fabric": ["fabric/src/main/resources/data/*/recipes"],
                },
                "target_roots": {
                    "fabric": "fabric",
                },
                "category_map": {
                    "fabric": "fabric",
                },
                "omit_globs": [],
                "target_protect_globs": ["fabric"],
                "rules": {},
            },
        },
        dry_run=False,
    )

    results = syncer.run()

    assert results["added"] == []
    assert results["updated"] == []
    assert results["removed"] == []
    assert (target / "fabric" / "cake.json").read_text() == "existing cake"


def test_mapping_sync_cancellation_carries_applied_mutations(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    recipe_dir = source / "fabric" / "src" / "main" / "resources" / "data" / "demo" / "recipes"
    recipe_dir.mkdir(parents=True)
    target.mkdir()
    (recipe_dir / "first.json").write_text("first")
    (recipe_dir / "second.json").write_text("second")
    cancel_event = threading.Event()

    def cancel_after_first_add(current, _total, operation):
        if operation == "Adding files" and current == 1:
            cancel_event.set()

    syncer = MCRU(
        {
            "source": str(source),
            "target": str(target),
            "parsers": [],
            "mapping": {
                "source_roots": {"fabric": ["fabric/src/main/resources/data/*/recipes"]},
                "target_roots": {"fabric": "fabric"},
                "category_map": {"fabric": "fabric"},
            },
        },
        progress_callback=cancel_after_first_add,
        cancel_event=cancel_event,
    )

    with pytest.raises(SyncCancelled) as caught:
        syncer.run()

    assert caught.value.results["added"] == ["fabric/first.json"]
    assert (target / "fabric" / "first.json").exists()


def test_threaded_mapping_cancellation_delivers_applied_mutations(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    recipe_dir = source / "fabric" / "src" / "main" / "resources" / "data" / "demo" / "recipes"
    recipe_dir.mkdir(parents=True)
    target.mkdir()
    (recipe_dir / "first.json").write_text("first")
    (recipe_dir / "second.json").write_text("second")
    completed = []
    syncer = None

    def on_progress(current, _total, operation):
        if operation == "Adding files" and current == 1:
            syncer.cancel()

    syncer = ThreadedSyncer(
        {
            "source": str(source),
            "target": str(target),
            "parsers": [],
            "mapping": {
                "source_roots": {"fabric": ["fabric/src/main/resources/data/*/recipes"]},
                "target_roots": {"fabric": "fabric"},
                "category_map": {"fabric": "fabric"},
            },
        },
        on_progress=on_progress,
        on_complete=lambda results, error: completed.append((results, error)),
    )
    syncer.start()

    assert syncer.wait(2)
    assert len(completed) == 1
    assert isinstance(completed[0][1], SyncCancelled)
    assert completed[0][0]["added"] == ["fabric/first.json"]
    assert (target / "fabric" / "first.json").exists()