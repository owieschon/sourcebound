# Current clean-docs product contract

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Repository maintainers use this contract to decide what a green clean-docs result actually
guarantees. It separates checked evidence from catalog visibility and authored judgment, so an
operator can choose the right gate without treating a passing receipt as proof of the whole corpus.
<!-- clean-docs:end purpose -->

**[Run the current operator workflow](#operator-workflows)**.

`clean-docs verify` is the proof: its receipt names the configured assurance scope and reports
direct bindings separately from cataloged surface.

## What clean-docs is

clean-docs is a local documentation-control engine and CLI. It binds selected documentation facts
to repository evidence, checks those relationships without a model, repairs declared regions, and
projects the same canonical pages for people and agents.

The repository manifest decides which facts receive direct protection. Static inventory makes
uncovered changes visible. Source-claim discovery can rank numeric counts and column-table identifiers,
but a repository must accept the exact document and source relationship before a deterministic
mismatch can gate. clean-docs does not infer product strategy, decide which concepts deserve
explanation, or certify unresolved prose.

## Assurance boundaries

The table below is part of the shipped capability registry:

<!-- clean-docs:begin assurance-boundaries -->
| surface | clean-docs proves | clean-docs does not prove |
| --- | --- | --- |
| Bound region, claim, or symbol | Configured evidence and documentation still agree | Unbound prose is accurate or complete |
| Repository catalog | Detected additions, removals, and replacements stay visible | Every cataloged item needs or has a reader-facing explanation |
| Accepted static source claim | The documented count or identifier set matches its accepted source locator | A ranked candidate names the right semantic relationship |
| Packaged writing policy | Implemented deterministic rules pass | Motivation, pedagogy, personality, or usefulness pass judgment |
| Authored purpose and scope | Declared markers and configured relationships remain intact | The repository chose the right goals, audience, or priority |
<!-- clean-docs:end assurance-boundaries -->

An outcome with `"ok": true` means the configured contract passed. Read
`outcomes.direct_coverage_complete` before claiming source-specific coverage across the detected
surface. A catalog entry is a change detector, not a prose claim.

## Operator workflows

Use `audit` before a manifest exists. It classifies each Markdown document by its job, applies
mechanically provable integrity defects, and previews only the page-shape and register rules that
fit that job. An untouched repository is assessment-only: integrity and compatible policy
candidates cannot become blockers. The default assessment reports mechanically witnessed
integrity candidates and repository-neutral corpus signals. `audit --preview-policy` adds bounded,
role-compatible house-policy candidates for compatibility review. A manifest accepts repository
integrity checks as gates; a document policy marker accepts compatible deterministic writing rules
for that page. Unclear ownership, process status, audience fit, historical marks, and text overlap
remain advisories in either state. The JSON report exposes the enforcement state, policy-preview
state, every document profile, advisory totals, unsupported MDX paths, and the exact accepted-debt
baseline under schema `clean-docs.audit.v1`. A maintainer can replace an ambiguous role guess with
a checked `<!-- clean-docs:role reference -->` marker; invalid role names fail instead of falling
back.

Use `init --no-model` once to add a repository-surface binding and `llms.txt`. It preserves existing
documents, repository-native structure, evidence records, and compatibility aliases. A new README
receives the packaged overview shape; an existing README keeps its authored opening unless it
already opted into the register. Otherwise, the generated catalog lives at
`.clean-docs/repository-surface.md`. Init stops instead of replacing an existing manifest,
overwriting its reserved generated file, or inventing purpose for an ambiguous page.

Use `check` for configured binding and projection drift. Use `check --changed --base REF --head REF`
to classify affected bindings, accepted source claims, and newly detected public surface.
Unsupported or uncovered public surface fails instead of becoming a no-impact claim.

Use `claims` to inspect ranked static source-to-prose candidates. Candidate ranking is
assessment-only. A `source_claim_checks` entry accepts one document anchor, subject, source path,
and locator as a gate without copying the expected value into configuration. Accepted checks fail
closed when either side disappears. Changed checks evaluate them only when the document, source,
or manifest changed.

Use `drive` to repair region bindings after deterministic policy checks. It does not rewrite
unbound prose. Run `project` afterward when a projection includes a repaired page, then run
`verify` for the combined audit, binding, projection, coverage, and optional changed-surface
receipt.

The [CLI reference](docs/CLI.md) owns the command index. Command-specific `--help` owns exact flags.

## Manifest contract

The canonical file is `.clean-docs.yml`, manifest version `1`. Unknown keys fail validation.

Current binding types are:

- `region`: extract typed evidence, render one marked block, and compare exact document bytes.
- `claim`: run one allowlisted JSON command and compare a typed value at an existing heading.
- `symbol`: prove that one cited path or Python symbol still exists.

The optional `source_claim_checks` list is separate from bindings because discovery and proof have
different authority. It supports `count` locators ending in `#count` and `identifier-set` locators
ending in `#keys`. A ranked relationship remains advisory; a committed relationship becomes part
of the configured contract.

Current projections are `llms.txt`, exact-byte context bundles, and the static recorded demo.
Plugins may add extractors, discoverers, renderers, and policy findings through process API version
`1`; they cannot replace first-party evidence or set coverage state.

The [manifest reference](docs/REFERENCE.md) owns accepted fields and examples. The
[extension reference](docs/EXTENSIONS.md) owns the plugin protocol.

## Evidence and execution

Static adapters parse Python, TypeScript, JavaScript, OpenAPI, JSON Schema, package metadata, and
configuration schemas without importing repository modules. A claim command or plugin runs only
when the manifest declares its exact argument array.

Declared processes receive a disposable repository copy, temporary directories, a minimal
environment, a timeout, an I/O limit, symlink checks, and secret-output checks. These controls are
not an operating-system sandbox. The [security model](docs/SECURITY_MODEL.md) owns the complete
boundary.

## Writing policy and model boundary

The packaged policy compiles from [`STANDARD.md`](STANDARD.md). `audit` and `drive` enforce its
implemented deterministic floor where each rule applies. `audit --preview-policy` reports
compatible policy candidates on unmarked documents as bounded advisories. The per-document profile
marker accepts those deterministic rules as gates, but cannot change a template or executable
agent procedure into an overview. Architecture records keep their time horizon. Evidence keeps its
observations, and references keep their lookup shape. A manifest accepts mechanically witnessed
repository integrity defects as gates; without one, audit reports them for assessment. The
complete standard also asks reviewers to judge why the page matters, how it teaches, where it
belongs, and whether its personality helps. A green mechanical result does not certify those
qualities.

The optional phrasing path accepts recorded provider output that selects at most five known fact
identifiers and allowlisted templates. Deterministic code renders the resulting sentences. Required
checks, CI, and release extraction do not need a model.

## Current non-goals

clean-docs does not:

- infer or authorize product goals, audience priorities, non-goals, or safety policy;
- decide that every detected symbol deserves reader documentation;
- treat a ranked source-claim candidate as proof or rewrite unrelated prose after a source change;
- use model judgment as a required gate;
- provide operating-system or network isolation;
- maintain a hosted service, account system, or runtime dashboard;
- send telemetry from the CLI;
- claim that generated prose reaches the quality of a skilled human writer.

## Compatibility

The 1.x line preserves manifest version `1`, plugin API version `1`, published machine schemas, and
stable command meanings. Minor releases may add optional fields. An incompatible manifest exits
`2` before extraction, and a removed stable surface requires a major release.

Use the [install guide](docs/INSTALL.md) for package and artifact lifecycle tasks. The
[support guide](docs/SUPPORT.md) owns CI pinning, corpus adoption, receipts, and diagnostics.
