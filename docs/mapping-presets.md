# Mapping Presets

Mapping presets let you route files from specific source folders into specific target subfolders instead of using plain source-to-target path mirroring.

Use mapping when your source has multiple platform/layout roots (for example common/fabric/forge) and your target needs a controlled output structure.

---

## What a mapping preset does

With no mapping preset, `mcru` compares:
- every file under `source`
- to the same relative path under `target`

With a mapping preset, `mcru`:
1. Resolves one or more source roots per category
2. Applies optional omit patterns (`omit_globs`)
3. Maps each remaining file into a configured target root
4. Syncs target to exactly that mapped result

Source is still authoritative.

---

## Where presets are stored

Default user file:
- `~/.mcru/mapping-presets.json`

Behavior:
- The file is seeded from bundled defaults on first run
- It is not overwritten during normal upgrades
- `mcru config reset-presets` re-copies bundled defaults

Optional override:
- `MCRU_MAPPING_FILE=/path/to/other-mapping-presets.json`

---

## Preset file shape

Top-level JSON format:

```json
{
  "version": 1,
  "presets": {
    "my-preset": {
      "description": "...",
      "source_roots": {},
      "target_roots": {},
      "category_map": {},
      "omit_globs": [],
      "target_protect_globs": [],
      "rules": {}
    }
  }
}
```

Each preset must include these keys:
- `source_roots`
- `target_roots`
- `category_map`
- `omit_globs`
- `rules`

If any are missing, preset loading fails.

---

## Option reference

### `description`
Human-readable text only.

### `source_roots`
Defines where source files are discovered, by source category.

Supported values per category:
- string glob
- list of string globs
- special object form for `forge_like` only:

```json
"forge_like": {
  "candidates": [
    "forge/src/main/resources/data/*/recipes",
    "neoforge/src/main/resources/data/*/recipes"
  ]
}
```

Notes:
- Globs are resolved relative to the profile/source path
- Only directories are accepted as roots
- For `forge_like`, candidate folders are resolved independently

### `target_roots`
Maps target categories to folders relative to profile `target`.

Example:

```json
"target_roots": {
  "common": "core",
  "fabric": "fabric",
  "forge_like": "forge"
}
```

A missing target category referenced by `category_map` causes an error.

### `category_map`
Maps source category names to target category names.

Example:

```json
"category_map": {
  "common": "common",
  "fabric": "fabric",
  "forge_like": "forge_like"
}
```

During sync, each source file discovered under a source category is written under that category's mapped target root.

### `omit_globs`
Excludes source files before mapping.

Patterns are checked against:
- full source-relative path (POSIX style)
- each individual path segment

Examples:
- `"**/minecraft/**"`
- `"temp"`
- `"*_backup"`

Important:
- `omit_globs` filters source-side inclusion
- It does not protect existing target files from deletion

### `target_protect_globs`
Excludes target files from mapped sync.

Patterns are checked the same way as `omit_globs`:
- full target-relative path (POSIX style)
- each individual path segment

Examples:
- `"fabric"`
- `"recipes/fabric/**"`
- `"**/legacy/**"`

Protected target paths are fully ignored:
- They are not deleted
- They are not compared
- They are not overwritten, even if a source file maps to the same target path

Important:
- This option applies only when a mapping preset is active
- It is optional; omitted presets behave as if it were an empty list

### `rules`
Rule object exists for behavior flags.

Currently relevant in code:
- `forge_like_conflict: "error_if_multiple"`

When this is set, and both `forge` and `neoforge` candidate roots resolve for `forge_like`, run fails with a clear conflict error.

Also present in bundled presets:
- `delete_mode: "global_target"`

Current behavior effectively uses global target pruning in mapping mode regardless of `delete_mode` value.

---

## Create a new preset

1. Open `~/.mcru/mapping-presets.json`
2. Add a new object under `presets`
3. Keep all required keys
4. Save file
5. Use it with profile or run flags

Example preset:

```json
{
  "version": 1,
  "presets": {
    "my-recipes-split": {
      "description": "Split recipes by platform and skip generated minecraft namespace",
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
        "common": "recipes/core",
        "fabric": "recipes/fabric",
        "forge_like": "recipes/forge"
      },
      "category_map": {
        "common": "common",
        "fabric": "fabric",
        "forge_like": "forge_like"
      },
      "omit_globs": [
        "**/minecraft/**",
        "temp",
        "*_backup"
      ],
      "target_protect_globs": [
        "recipes/neoforge/**"
      ],
      "rules": {
        "forge_like_conflict": "error_if_multiple",
        "delete_mode": "global_target"
      }
    }
  }
}
```

---

## Use presets

Assign to profile:

```bash
mcru profile add recipes ./my-mod ./target-pack --mapping my-recipes-split
mcru profile update recipes ./my-mod ./target-pack --mapping my-recipes-split
mcru profile set recipes --mapping my-recipes-split
```

Override on run:

```bash
mcru run recipes --mapping my-recipes-split
mcru quick ./my-mod ./target-pack --mapping my-recipes-split
```

Effective precedence:
1. `--mapping` on `run`/`quick`
2. profile `mapping_preset`
3. no mapping (default mirroring)

---

## Validate before live runs

Use a dry-run first:

```bash
mcru run recipes --dry-run
```

Use profile snapshot to confirm mapped scope:

```bash
mcru profile snapshot recipes
```

With mapping enabled, snapshot source/target scope is limited to mapped roots.

---

## Can two different profiles write to one shared target safely?

Yes, when each mapping preset protects the other profile's target subtree with `target_protect_globs`.

Example shared target layout:

```text
target-pack/
  fabric/
  neoforge/
```

Fabric profile preset:

```json
"target_roots": {
  "fabric": "fabric"
},
"target_protect_globs": [
  "neoforge"
]
```

NeoForge profile preset:

```json
"target_roots": {
  "neoforge": "neoforge"
},
"target_protect_globs": [
  "fabric"
]
```

With this setup, each profile can update its own mapped output and fully ignore the other profile's folder.

Important:
- This requires mapping mode
- Protection applies to files already in the target as well as source files that would map into the protected target path
- Run `--dry-run` first when introducing a shared target

If both platforms are in one source tree, a single profile/preset that maps both outputs remains simpler.

---

## Can I omit folders that are already correct?

Yes.

Use:
- `omit_globs` to skip source files before mapping
- `target_protect_globs` to fully ignore existing target files/folders during mapped sync
