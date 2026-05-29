"""Tests for mapped sync behavior."""

from syncer import MCRU


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