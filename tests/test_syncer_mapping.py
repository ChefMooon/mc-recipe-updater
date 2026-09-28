"""Tests for mapped sync behavior."""

import threading
from pathlib import Path

import pytest

from syncer import MCRU, SyncCancelled
from tui.utils import ThreadedSyncer


@pytest.mark.parametrize(
    ("invalid_roots", "expected_error", "error_message"),
    [
        ("source_file", NotADirectoryError, "Source path is not a directory"),
        ("target_file", NotADirectoryError, "Target path is not a directory"),
        ("overlap", ValueError, "must not be the same or overlap"),
    ],
)
def test_mapping_sync_rejects_invalid_roots_before_mapping_or_mutation(
    tmp_path, monkeypatch, invalid_roots, expected_error, error_message
):
    source = tmp_path / "source"
    target = tmp_path / "target"

    if invalid_roots == "source_file":
        source.write_text("source contents")
        target.mkdir()
        target_file = target / "keep.json"
        target_file.write_text("target contents")
        source_file = source
    elif invalid_roots == "target_file":
        source.mkdir()
        source_file = source / "fabric.json"
        source_file.write_text("source contents")
        target.write_text("target contents")
        target_file = target
    else:
        source = target / "source"
        source.mkdir(parents=True)
        source_file = source / "fabric.json"
        source_file.write_text("source contents")
        target_file = target / "keep.json"
        target_file.write_text("target contents")

    def fail_mapping_traversal(_syncer):
        pytest.fail("mapping traversal must not run for invalid roots")

    monkeypatch.setattr(MCRU, "_build_source_target_map", fail_mapping_traversal)

    with pytest.raises(expected_error, match=error_message):
        MCRU(
            {
                "source": str(source),
                "target": str(target),
                "parsers": [],
                "mapping": {
                    "source_roots": {"fabric": ["fabric"]},
                    "target_roots": {"fabric": "fabric"},
                    "category_map": {"fabric": "fabric"},
                },
            },
            dry_run=False,
        )

    assert source_file.read_text() == "source contents"
    assert target_file.read_text() == "target contents"
    assert list(tmp_path.rglob(".mcru-transaction-*")) == []


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


def test_mapped_later_removal_failure_rolls_back_prior_update(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    recipe_dir = source / "fabric" / "src" / "main" / "resources" / "data" / "demo" / "recipes"
    recipe_dir.mkdir(parents=True)
    target_recipe_dir = target / "fabric"
    target_recipe_dir.mkdir(parents=True)
    (recipe_dir / "cake.json").write_text("new cake")
    (target_recipe_dir / "cake.json").write_text("old cake")
    remove_file = target_recipe_dir / "obsolete.json"
    remove_file.write_text("preserve me")
    original_unlink = Path.unlink

    def fail_mapped_removal(path, *args, **kwargs):
        if path == remove_file:
            raise OSError("injected mapped removal failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_mapped_removal)
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
    )

    results = syncer.run()

    assert (target_recipe_dir / "cake.json").read_text() == "old cake"
    assert remove_file.read_text() == "preserve me"
    assert results["updated"] == []
    assert results["removed"] == []
    assert results["rollback_complete"] is True
    assert results["rollback_errors"] == []
    assert results["errors"][0] == ("fabric/obsolete.json", "injected mapped removal failure")