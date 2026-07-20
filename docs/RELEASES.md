# Grounded release notes

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Maintainers use this guide to build release notes from the difference between two repository refs.
It keeps the factual delta independent of a narrative draft, so missing, altered, duplicated, or
uncited changes fail before publication.
<!-- sourcebound:end purpose -->

**[Render the factual skeleton](#render-the-factual-skeleton)**.

The JSON result is the proof: every delta carries its source, locator, adapter, and evidence digest.

## Render the factual skeleton

`release` inventories each ref in its own snapshot, compares normalized evidence, and emits added, removed, and changed facts. Run it without a model or network:

```bash
sourcebound release --from v0.4.0 --to HEAD
```

Use `--format json` when another tool needs the typed `sourcebound.release-delta.v1` record. Each delta carries its source, locator, adapter, and before or after evidence digest.

## Validate a narrative draft

Narrative text is optional and cannot replace the factual section. Replay a recorded response with:

```bash
sourcebound release \
  --from v0.4.0 \
  --to HEAD \
  --recorded-model-response release-draft.json
```

The response must use `sourcebound.release-narrative.v1`. Every draft mirrors the delta ID, change, kind, name, and `source#locator` citation. sourcebound withholds the entire narrative and exits `1` if a draft omits a delta, changes a deterministic field, duplicates a delta, misses its citation, or violates the packaged prose policy.

The factual Markdown and JSON remain unchanged when narrative validation fails. A recorded result describes that response only; it does not make a claim about another provider or model.

## Current boundary

Release extraction is static and snapshot-bound. First-party and configured discoverer plugins run once per ref in disposable copies. The active worktree, its installed dependencies, and narrative output cannot change the typed delta.

This command describes another repository's release. Workflows publish sourcebound itself, and
repository-hosted issues hold reader-trial records. Neither belongs in this feature guide.
