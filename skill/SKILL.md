---
name: sourcebound
description: Audit repository documentation, repair bound facts, and verify that committed docs match their sources and the packaged standard.
---

# Maintain repository documentation

<!-- sourcebound:purpose -->
Use sourcebound when documentation may have drifted, when a repository needs a corpus audit,
or before publishing a change that affects bound facts. This procedure gives maintainers a read-only audit, a bounded repair path, and the gates that prove source-bound docs are current.
<!-- sourcebound:end purpose -->

## Audit without configuration

Run the manifest-free corpus audit first:

```bash
sourcebound audit
```

Resolve every reported local-link, process-artifact, and unjustified-length finding. Move
historical process material under `docs/archive/`; keep current product truth on the active
reader surface.

## Repair configured documentation

When `.sourcebound.yml` exists, repair generated regions and validate the result:

```bash
sourcebound drive
```

`drive` writes only declared regions. It preserves prose outside their markers and refuses
to write when an implemented policy check fails.

## Verify before publishing

Run the read-only gates after repair:

```bash
sourcebound audit
sourcebound check
```

For sourcebound itself, also run the independent self-hosting gate:

```bash
python3 scripts/trusted_self_check.py
```

Use `--format json` when another tool needs structured findings. A drift or audit finding
exits `1`; malformed configuration exits `2`; extraction failures exit `3`.

## Preserve review issues as candidates

When a review finds a problem that the current audit does not express, record it once as
`sourcebound.review-observations.v1`, then compile its documentation and product test tracks:

```bash
sourcebound review candidates \
  --input .sourcebound/reviews/REVIEW.json \
  --out .sourcebound/improvement-candidates.json
```

Do not implement a candidate until its observation is reproduced and its proposed test has a
fixture and assertion. Candidate output has neither change nor gate authority.

Initialize and preserve its assessment-only lifecycle before acting on it:

```bash
sourcebound review lifecycle init \
  --input .sourcebound/reviews/REVIEW.json \
  --out .sourcebound/improvement-lifecycle.json
```

Advance only adjacent states with a typed issue, commit, decision, or test-receipt reference. The
lifecycle links evidence; it does not accept the change or alter an ordinary gate.
