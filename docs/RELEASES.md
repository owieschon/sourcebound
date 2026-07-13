# Grounded release notes

This page explains how to produce release facts from two immutable repository refs.

## Render the factual skeleton

`release` inventories each ref in its own snapshot, compares normalized evidence, and emits added, removed, and changed facts. Run it without a model or network:

```bash
clean-docs release --from v0.4.0 --to HEAD
```

Use `--format json` when another tool needs the typed `clean-docs.release-delta.v1` record. Each delta carries its source, locator, adapter, and before or after evidence digest.

## Validate a narrative draft

Narrative text is optional and cannot replace the factual section. Replay a recorded response with:

```bash
clean-docs release \
  --from v0.4.0 \
  --to HEAD \
  --recorded-model-response release-draft.json
```

The response must use `clean-docs.release-narrative.v1`. Every draft mirrors the delta ID, change, kind, name, and `source#locator` citation. clean-docs withholds the entire narrative and exits `1` if a draft omits a delta, changes a deterministic field, duplicates a delta, misses its citation, or violates the packaged prose policy.

The factual Markdown and JSON remain unchanged when narrative validation fails. A recorded result describes that response only; it does not make a claim about another provider or model.

## Current boundary

Release extraction is static and snapshot-bound. First-party and configured discoverer plugins run once per ref in disposable copies. The active worktree, its installed dependencies, and narrative output cannot change the typed delta.

Release-candidate builds rehearse the published reader tasks in CI. A stable release additionally requires content-addressed receipts from at least one independent human reader and one independent agent reader. Each participant must use only the rubric's published context, complete every task, and bind the resulting evidence by SHA-256. The receipt also names the exact candidate commit and wheel digest. `scripts/verify_reader_trial.py` checks `.clean-docs/reader-trial.json`; `scripts/build_release.py` reconstructs the candidate wheel and permits only the version and reader receipts to differ in the stable release. It refuses absent, incomplete, stale, tampered, or untried evidence.
