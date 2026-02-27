# Solved Issues

A running log of bugs that were diagnosed and fixed. Kept for future reference and to guide similar investigations.

---

## [2026-02-27] Forge/NeoForge Conflict Error Triggered by Multi-Namespace Mods

### Symptom

Running `mcru run <profile>` with the `mc-arch` mapping against a multi-namespace mod source threw:

```
Both forge and neoforge source folders were found; expected only one.
Found: ...forge\src\main\resources\data\farmersdelight\recipes,
       ...forge\src\main\resources\data\frightsdelight\recipes
```

The source folder did not contain a `neoforge/` directory at all.

### Root Cause

`_resolve_source_dirs()` in `syncer.py` resolved **all** `forge_like` candidates in a single `_resolve_glob_dirs()` call, which returned every directory matching any of the two glob patterns (`forge/...` and `neoforge/...`) as one flat list.

The conflict check `len(matches) > 1` fired whenever that flat list had more than one entry — meaning **multiple data namespaces under a single platform** (e.g. `farmersdelight/recipes` and `frightsdelight/recipes` both inside `forge/`) incorrectly triggered the error, even though no NeoForge folder existed at all.

The underlying project also had a `forge/` subfolder inside `data/forge/`, which was another valid match under the same glob pattern, contributing an additional hit.

### Fix

Changed `_resolve_source_dirs()` to resolve **each candidate pattern independently**, then check whether more than one *candidate* produced matches — not whether there were more than one match in total.

**Before:**

```python
matches = self._resolve_glob_dirs(candidates)
if len(matches) > 1 and rules.get("forge_like_conflict") == "error_if_multiple":
    raise ValueError(...)
```

**After:**

```python
per_candidate = [self._resolve_glob_dirs([c]) for c in candidates]
active = [matches for matches in per_candidate if matches]
if len(active) > 1 and rules.get("forge_like_conflict") == "error_if_multiple":
    raise ValueError(...)
```

Now the error only fires when both `forge/` **and** `neoforge/` patterns resolve to at least one directory — a genuine cross-platform ambiguity. Multiple namespaces under a single platform are handled correctly.

### Files Changed

- `syncer.py` — `_resolve_source_dirs()`, lines ~294–308
