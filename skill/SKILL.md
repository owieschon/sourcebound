---
name: clean-docs
description: Audit repository documentation, repair bound facts, and verify that committed docs match their sources and the packaged standard.
---

# Maintain repository documentation

<!-- clean-docs:purpose -->
Use clean-docs when documentation may have drifted, when a repository needs a corpus audit,
or before publishing a change that affects bound facts. This procedure gives maintainers a read-only audit, a bounded repair path, and the gates that prove source-bound docs are current.
<!-- clean-docs:end purpose -->

## Audit without configuration

Run the manifest-free corpus audit first:

```bash
clean-docs audit
```

Resolve every reported local-link, process-artifact, and unjustified-length finding. Move
historical process material under `docs/archive/`; keep current product truth on the active
reader surface.

## Repair configured documentation

When `.clean-docs.yml` exists, repair generated regions and validate the result:

```bash
clean-docs drive
```

`drive` writes only declared regions. It preserves prose outside their markers and refuses
to write when an implemented policy check fails.

## Verify before publishing

Run the read-only gates after repair:

```bash
clean-docs audit
clean-docs check
```

For clean-docs itself, also run the independent self-hosting gate:

```bash
python3 scripts/trusted_self_check.py
```

Use `--format json` when another tool needs structured findings. A drift or audit finding
exits `1`; malformed configuration exits `2`; extraction failures exit `3`.
