# Grounded release notes

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this guide when release notes must describe the difference between two repository refs without trusting a narrative draft to choose the changes. It shows maintainers how to render the source-bound delta and reject prose that omits, alters, duplicates, or uncites a fact.
<!-- clean-docs:end purpose -->

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

Release-candidate builds rehearse the published reader tasks in CI. A stable release additionally requires one content-addressed trial from each profile in that release line's rubric:

| Release line | Independent reader set | Evidence contract |
| --- | --- | --- |
| `1.0` | Anthropic Opus 4.8, Anthropic Sonnet 5, Codex GPT 5.5 High, and Codex GPT 5.6 Sol High | Product identification, installation, protection, repair, and limitation tasks |
| `1.1` | Anthropic Opus 4.8 and Codex GPT 5.6 Sol High | Learning-path routing, tutorial execution, and deterministic-authority tasks |

Every profile runs in a fresh session with only the rubric's published context, completes every task, and binds its evidence by SHA-256. Profiles cannot share conversation history or prior trial output. The receipt also names the exact candidate commit and wheel digest. `scripts/verify_reader_trial.py` selects the versioned rubric and evidence namespace; `scripts/build_release.py` reconstructs the candidate wheel and permits only the version and matching reader receipts to differ in the stable release. It refuses absent, duplicate, substituted, incomplete, stale, tampered, or untried evidence.
