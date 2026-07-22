# Sourcebound

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Sourcebound is a documentation engine and CLI for maintainers who need code and prose to change together. It binds selected claims to their defining sources, so drifted documentation fails locally and in CI instead of reaching readers.
<!-- sourcebound:end purpose -->

[![CI](https://github.com/owieschon/sourcebound/actions/workflows/ci.yml/badge.svg)](https://github.com/owieschon/sourcebound/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/owieschon/sourcebound?display_name=tag&sort=semver)](https://github.com/owieschon/sourcebound/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-25225f.svg)](LICENSE)

**[Install the stable release and catch your first stale claim](docs/learn/tutorial-catch-a-lying-doc.md)**.

The final `sourcebound verify` command prints a [`sourcebound.outcome.v2` receipt](docs/SUPPORT.md#record-local-outcomes) with `"ok": true`.

Before adoption, `audit` reports bounded repository-neutral advisories. A manifest turns integrity checks into gates; policy markers opt compatible writing rules into specific documents. Neither authorizes Sourcebound to flatten repository-native forms.

| If you need to... | Start with | You will leave with... |
| --- | --- | --- |
| Try the repair loop | [Runnable tutorial](docs/learn/tutorial-catch-a-lying-doc.md) | A failed drift check and a repaired page |
| Adopt Sourcebound in an existing repository | [Support guide](docs/SUPPORT.md) | A narrow, reviewable first gate |
| Configure a binding | [Manifest reference](docs/REFERENCE.md) | A source-bound fact with the right depth |
| Choose a command | [CLI reference](docs/CLI.md) | The command and its write boundary |
| Review a pull request | [Coverage-stating verdict](docs/CLI.md#pull-request-verdicts) | One pinned state with gaps, skips, and non-claims visible |
| Choose the right documentation tool | [Ecosystem fit](docs/ECOSYSTEM.md) | One owner for each kind of defect |
| Understand trust boundaries | [Security model](docs/SECURITY_MODEL.md) | The process and host guarantees |

## Why Sourcebound exists

<!-- sourcebound:begin product-overview -->
A stale sentence does not fail loudly. It keeps a straight face after the code has moved on, and reviewers have no mechanical way to identify the false claim. Sourcebound gives each protected fact a source, then checks that relationship again in CI.

Declared sources own the protected facts. A packaged policy enforces the deterministic form floor; authored judgment still owns motivation, pedagogy, and voice. Static adapters read common code and schema formats, while declared commands run under explicit process controls. The engine can repair bound regions, rank static count and column candidates, enforce accepted source-claim relationships, and project canonical text and visual records into purpose-built human and agent surfaces with local receipts.
<!-- sourcebound:end product-overview -->

Human review can improve a sentence. It cannot make the sentence fail when its defining source changes. The [deterministic seam](docs/learn/deep-dive-the-deterministic-seam.md) explains how Sourcebound separates source evidence, optional phrasing, and gate authority.

## Use Sourcebound when

Use Sourcebound when an authored explanation contains a selected fact with a stable owner in code, configuration, a schema, or a registry. For example, a public action table can derive from `ACTIONS` in `src/actions.py`; a source-only rename makes `check` fail, and `drive` updates only the declared table region. The [tutorial](docs/learn/tutorial-catch-a-lying-doc.md) runs that exact loop.

Use another tool when it owns the job better. Vale can own prose mechanics. Doc Detective can own whether a consequential procedure still works. A generator can own an entire API or schema reference. If those tools already cover the facts you need, Sourcebound may not justify another gate. The [ecosystem guide](docs/ECOSYSTEM.md) names the boundary.

## Install in the repository you want to protect

Install the stable CLI in an isolated environment, then run the manifest-free audit from the
repository you want to protect:

```bash
pipx install sourcebound
sourcebound audit
```

Use `uv tool install sourcebound` instead when `uv` owns your command-line tools. The
[installation guide](docs/INSTALL.md) covers offline wheelhouses, upgrades, and rollback. The
[release verification guide](docs/VERIFY_RELEASE.md) checks published bytes and provenance.

After reviewing the assessment, inspect the files that `init` proposes before accepting its gate:

<!-- sourcebound:allow-inline-document target=".sourcebound/repository-surface.md" reason="Init conditionally creates this reserved output for an established unregistered README" -->

```bash
sourcebound init --no-model
git diff -- .sourcebound.yml .sourcebound/repository-surface.md README.md llms.txt
sourcebound check
sourcebound verify
```

An established, unregistered README stays byte-for-byte authored. Init writes its detected catalog to `.sourcebound/repository-surface.md`; a new README or one that adopted the register may own that region directly. Its plan also reports zero directly protected prose after catalog-only setup and lists bounded advisory source-claim candidates when static ownership evidence supports them. Review a candidate, then add its exact relationship manually or reject it.

After a bound source changes, run `check`, then use `drive` for a declared repair. Run `project` when a declared projection depends on the repaired document, then run `verify`. The [tutorial](docs/learn/tutorial-catch-a-lying-doc.md) shows the failure before the repair; the [support guide](docs/SUPPORT.md) covers mature-repository adoption.

## How the pieces fit

`authored intent + repository contract + change state → typed evidence → bounded check, repair, projection, and receipt`

**Authored intent** states what the maintainers want readers to know. Sourcebound does not infer its priority, completeness, or editorial quality. **Repository contract** selects the facts and relationships that earn deterministic treatment. Each mechanism proves only its declared relationship: accepted source-claim checks are separate from generated regions, and unbound prose stays visibly unknown.

An immutable impact plan fixes the changed scope before a check reports on it. This gives the repository four job-specific exits: `drive` writes only planned regions; `check` and `verdict` are read-only; `project` writes declared outputs; and `verify` emits its own outcome receipt. `verdict` and `verify` produce independent receipts. Neither certifies unbound or judgment prose.

The [architecture reference](docs/ARCHITECTURE.md#documentation-flow) and [product contract](SOURCEBOUND_SPEC.md)
name each boundary in detail.

## Current boundaries

- Catalog coverage detects source additions, removals, and replacements; it does not validate prose.
- Source-claim discovery ranks static count and identifier-set candidates. A candidate remains advisory until the repository accepts its exact document and source relationship.
- Declared processes use time, I/O, and environment controls. The host owns network isolation; see the [security model](docs/SECURITY_MODEL.md).
- The manifest decides what Sourcebound evaluates. Authored purpose records goals; Sourcebound does not infer or certify them.
- Feedback is off by default. Enabled runs queue bounded local envelopes; only an explicit `feedback flush` contacts the configured sink, and delivery cannot change a gate result.

Use the [learning path](docs/learn/index.md) for examples. The [product contract](SOURCEBOUND_SPEC.md) owns parser, write-boundary, and exit-code details.
