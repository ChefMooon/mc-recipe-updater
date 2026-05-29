# Folder Mapping

Mapping mode is enabled with `--mapping <preset-name>`.

- If no mapping is set (CLI or profile), normal workflow is used: all files are matched by relative path.
- If mapping is set, files are read from mapped source categories and copied into mapped target folders.
- If `target_protect_globs` is set, matching target paths are fully ignored during mapped sync.

## Mapping presets location

Presets are stored at `~/.mcru/mapping-presets.json`.

This file is automatically seeded from the bundled package defaults the first time `mcru` runs.
You can freely edit it to add or modify presets — package upgrades will never overwrite your copy.

To reset presets to package defaults, use:
```bash
mcru config reset-presets
```

You can also override the mapping file path by setting the `MCRU_MAPPING_FILE` environment variable.

## Preset: `mc-arch`

### Source categories

- `common`: `common/src/generated/resources/data/*/recipes`
- `fabric`: `fabric/src/main/resources/data/*/recipes`
- `forge_like.candidates`:
    - `forge/src/main/resources/data/*/recipes`
    - `neoforge/src/main/resources/data/*/recipes`

Rule: if both forge and neoforge candidates resolve at the same time, sync fails with a clear error.

### Target categories

- `common` -> `core`
- `fabric` -> `fabric`
- `forge_like` -> `forge`

### Full preset schema

```json
{
    "version": 1,
    "presets": {
        "mc-arch": {
            "description": "Map multi-platform Minecraft recipe sources into core/fabric/forge target folders.",
            "source_roots": {
                "common": ["common/src/generated/resources/data/*/recipes"],
                "fabric": ["fabric/src/main/resources/data/*/recipes"],
                "forge_like": {
                    "candidates": [
                        "forge/src/main/resources/data/*/recipes",
                        "neoforge/src/main/resources/data/*/recipes"
                    ]
                }
            },
            "target_roots": {
                "common": "core",
                "fabric": "fabric",
                "forge_like": "forge"
            },
            "category_map": {
                "common": "common",
                "fabric": "fabric",
                "forge_like": "forge_like"
            },
            "omit_globs": [],
            "target_protect_globs": [],
            "rules": {
                "forge_like_conflict": "error_if_multiple",
                "delete_mode": "global_target"
            }
        }
    }
}
```

## Omit globs

Use `omit_globs` to exclude source paths or folder/file names.

Examples:

- `"**/minecraft/**"`
- `"temp"`
- `"*_backup"`

## Target protect globs

Use `target_protect_globs` to fully ignore target paths during mapped sync.

Matching target files are not deleted, compared, or overwritten. This is useful when two mapping profiles share the same target folder but own different subfolders.

Examples:

- `"fabric"`
- `"recipes/fabric/**"`
- `"**/legacy/**"`