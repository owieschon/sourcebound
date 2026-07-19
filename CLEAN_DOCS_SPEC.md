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
| Generated region | Rendered region bytes match configured source evidence | Authored prose outside the region is accurate or complete |
| Legacy command pin (`type: claim`) | Allowlisted command output matches the configured expected value and the document anchor exists | The prose under that anchor states the command result |
| Symbol reference | The configured source path or Python symbol exists | The surrounding prose describes that symbol accurately |
| Repository catalog | Detected additions, removals, and replacements stay visible | Every cataloged item needs or has a reader-facing explanation |
| Accepted static source claim | The documented count or identifier set matches its accepted source locator | A ranked candidate names the right semantic relationship |
| Binding sensitivity receipt | One static check becomes stale after one independently frozen source fact changes | The document and source describe the same concept or that the relationship should be accepted |
| Declared review contract | At two immutable refs, repository-declared source locators changed without every declared target locator changing | The target is stale, a co-change is semantically correct, or the locators describe the same concept |
| Pull-request verdict | Static configured checks and changed-surface evidence produce the reported state at one pinned commit | Unbound prose, skipped processes, semantic relationships, or authored judgment are correct |
| Packaged writing policy | Implemented deterministic rules pass | Motivation, pedagogy, personality, or usefulness pass judgment |
| Authored purpose and scope | Declared markers and configured relationships remain intact | The repository chose the right goals, audience, or priority |
| Opt-in feedback loop | Validated operational envelopes and improvement-state receipts satisfy their closed schemas | Observed behavior establishes causality, authorizes purpose, or makes a candidate change correct |
<!-- clean-docs:end assurance-boundaries -->

An outcome with `"ok": true` means the configured contract passed. Read
`outcomes.direct_coverage_complete` before claiming source-specific coverage across the detected
surface. A catalog entry is a change detector, not a prose claim.

## Operator workflows

Use `audit` before a manifest exists. It classifies each Markdown or structurally valid MDX document by its job, applies
mechanically provable integrity defects, and previews only the page-shape and register rules that
fit that job. An untouched repository is assessment-only: integrity and compatible policy
candidates cannot become blockers. The default assessment reports mechanically witnessed
integrity candidates and repository-neutral corpus signals. `audit --preview-policy` adds bounded,
role-compatible house-policy candidates for compatibility review. A manifest accepts repository
integrity checks as gates; a document policy marker accepts compatible deterministic writing rules
for that page. Unclear ownership, process status, audience fit, historical marks, and text overlap
remain advisories in either state. The JSON report exposes the enforcement state, policy-preview
state, every document profile, advisory totals, unsupported MDX paths, and the exact accepted-debt
baseline under `clean-docs.audit-baseline.v2`. Baseline identity uses rule, path, normalized
offending content, section anchor, and duplicate ordinal. A line number is display metadata, so
moving unchanged debt does not manufacture a new finding. Version 1 baselines remain readable and
`audit --update-baseline` migrates them. A maintainer can replace an ambiguous role guess with a
checked `<!-- clean-docs:role reference -->` marker; invalid role names and unclosed opening
frontmatter fail instead of falling back. Placeholder destinations remain non-blocking only in
templates and agent procedures. Literal machine paths in recognized test fixtures remain
advisories because they can be intentional inputs; the same path in product source or a lockfile
remains an integrity finding.

Use `init --no-model` once to add a repository-surface binding and `llms.txt`. It preserves existing
documents, repository-native structure, evidence records, and compatibility aliases. A new README
receives the packaged overview shape; an existing README keeps its authored opening unless it
already opted into the register. Otherwise, the generated catalog lives at
`.clean-docs/repository-surface.md`. The initial context projection contains that catalog and the
root orientation page only; clean-docs does not promote architecture records, examples, or nested
READMEs to canonical context from their filenames. Init stops instead of replacing an existing
manifest, overwriting its reserved generated file, or inventing purpose for an ambiguous page.

Use `check` for configured binding and projection drift. Use `check --changed --base REF --head REF`
to classify affected bindings, accepted source claims, and newly detected public surface.
Unsupported or uncovered public surface fails instead of becoming a no-impact claim.

Use `plan --base REF --head REF` to produce a read-only impact receipt before repair. The planner
uses the merge base, classifies every changed artifact, and traverses only affected accepted
bindings, projections, and evaluations. `impact: none` requires complete adapter coverage;
unsupported public candidates remain `unknown`. The receipt binds its producer version, immutable
Git objects, manifest, graph, and findings. The first-party MDX adapter parses source positions,
frontmatter, Markdown nodes, ESM syntax, JSX structure, expressions, comments, and fenced code
without resolving or executing imports. Valid MDX enters the checked document count. Malformed MDX
or a missing Node.js 20 runtime appears in `unsupported_documents` and makes the impact `unknown`.
The command's zero exit code means the receipt was built, not that the branch is ready to merge.

Use `review_contracts` to declare exact source and documentation locators that deserve attention
together. The contract is observe-only. clean-docs compares locator digests at two immutable refs;
it does not infer relationships from filenames, imports, repository history, or prior co-change.
A changed source with an unchanged target is `review-recommended`. A changed source whose every
target also changed is `cochanged`. Both states are advisory. They cannot enter required coverage,
change gate status, or authorize a write. A co-change records two changes, not completed review or
semantic correctness. A missing co-change recommends review; it does not prove the target is stale.
Review-contract graph edges record observation topology only. They do not make an artifact covered
or change `coverage_complete`. The evaluator reads each path once per immutable ref and reuses
syntax parses and locator digests within the run. Markdown section boundaries come from parsed
Markdown and MDX headings, so headings inside comments, code, frontmatter, expressions, ESM blocks,
and lowercase HTML flow blocks do not define sections. The
[manifest reference](docs/REFERENCE.md#review-contracts) owns the fixed cardinality and input
budgets. A manifest above a cardinality limit is invalid. A read, parse, or input-budget failure
makes the affected observation `unknown`; it does not become gate authority.

Use `verdict --base REF --head REF --format json` for one pull-request decision. It composes the
audit, static binding, projection, accepted source-claim, changed-surface, impact, and inventory
library results without executing repository commands or plugins. `ready` means ready only within
the named `required-gates-and-changed-surface` scope. The `gate` axis controls the exit code through
`ready`, `not_ready`, or `unknown`. The separate `observations` axis reports `clear`,
`review-recommended`, or `unknown` and never controls the exit code. Top-level `state` and `ready`
remain compatibility aliases for `gate`. A ready gate can therefore coexist with incomplete
observations. The receipt lists sparse coverage, skipped execution, unsupported documents, and six
explicit non-claims, so a partial gate cannot present itself as corpus-wide proof. The
[CLI contract](docs/CLI.md#pull-request-verdicts) owns the schema and exit meanings.

Use the [reusable gate](docs/SUPPORT.md#run-the-reusable-pull-request-gate) to carry that verdict
through GitHub Actions. No target process starts. The workflow runs one static verdict, renders SARIF from the recorded JSON,
hashes every evidence file, and derives its job result from the validated verdict bytes. It has
read-only repository permission and no input that enables repository commands or plugins. Python
runs in isolated mode, while transport evidence stays outside the inspected checkout.

Use the [read-only verification skill](skills/clean-docs-verify/SKILL.md) when an external agent
needs the same boundary outside the reusable workflow. It cannot repair. The skill limits the agent to static
inventory, claims, impact, verdict, and independently frozen sensitivity receipts. The existing
maintenance skill remains the explicit repair path.

Use `claims` to inspect ranked static source-to-prose candidates. Candidate ranking is
assessment-only. It requires a subject match plus ownership evidence from the document heading,
file stem, or directory. Path depth alone cannot establish ownership. The report states the full
candidate population, the bounded count shown, and any truncation. A `source_claim_checks` entry
accepts one document anchor, subject, source path, and locator as a gate without copying the
expected value into configuration. Accepted checks fail closed when either side disappears.
Changed checks evaluate them only when the document, source, or manifest changed.

Use `binding sensitivity` only after an independent process freezes a source fact. The command
renames one supported static mapping member inside a disposable copy and reports whether the
selected check becomes stale. A `sensitive` result proves dependency on that fact. It does not
prove that the prose and source describe the same concept, and it never accepts the relationship.
The proposal and fact travel as separate, digested inputs so a provider cannot choose the mutation
that scores its own proposal.

Use `drive` to repair region bindings after deterministic policy checks. It does not rewrite
unbound prose. Run `project` afterward when a projection includes a repaired page, then run
`verify` for the combined audit, binding, projection, coverage, and optional changed-surface
receipt.

Use `feedback` only after an operator explicitly enables a named sink. Normal runs then write
bounded local `clean-docs.feedback.v1` envelopes; they still make no network request. `preview`
shows pending envelope bytes and `flush` performs delivery. Capture and delivery never participate
in an audit, check, verdict, or verify result.

An external controller may return an aggregate `clean-docs.behavior-signal.v1`. Ingest records it
as an observed hypothesis. Each later step needs its own receipt: reproduce the problem, classify
its cause, propose a test, add a failing fixture, measure the candidate in shadow, prepare the
change, and submit an ordinary verified pull request. Behavior is evidence about outcomes, not
authority over product purpose or deterministic policy. The
[feedback contract](docs/FEEDBACK.md) owns consent and delivery. The
[behavior-signal contract](docs/BEHAVIOR_SIGNALS.md) owns the return path.

The [CLI reference](docs/CLI.md) owns the command index. Command-specific `--help` owns exact flags.

## Manifest contract

The canonical file is `.clean-docs.yml`. Init writes manifest version `2`; version `1` remains a
readable compatibility format. Unknown keys fail validation.

Current binding types are:

- `region`: extract typed evidence, render one marked block, and compare exact document bytes.
- `claim`: run one allowlisted JSON command and compare a typed value at an existing heading.
- `symbol`: prove that one cited path or Python symbol still exists.

The optional `source_claim_checks` list is separate from bindings because discovery and proof have
different authority. It supports `count` locators ending in `#count` and `identifier-set` locators
ending in `#keys`. A ranked relationship remains advisory; a committed relationship becomes part
of the configured contract.

The optional `review_contracts` list is separate from bindings and accepted source claims. It
records repository-declared source and target locators for advisory co-change evidence. It never
creates repair or gate authority. The [review-contract reference](docs/REFERENCE.md#review-contracts)
owns its locator rules, tautology guards, work limits, and state meanings.

Current projections are `llms.txt`, exact-byte context bundles, and the static recorded demo.
Provider context can also be compiled as a read-only, source-addressed
`clean-docs.context-bundle.v1`. The request pins the repository commit and each source line range.
Selection is deterministic under a byte budget, and every exclusion carries a reason. Only accepted
policy may grant instruction authority; repository prose remains evidence data.

Plugins may add extractors, discoverers, renderers, and policy findings through process API version
`1`; they cannot replace first-party evidence or set coverage state.

The [manifest reference](docs/REFERENCE.md) owns accepted fields and examples. The
[extension reference](docs/EXTENSIONS.md) owns the plugin protocol.

## Evidence and execution

Static adapters parse Python, TypeScript, JavaScript, OpenAPI, JSON Schema, package metadata, and
configuration schemas without importing repository modules. Immutable read-only snapshots preserve
relative symlinks whose targets stay inside the snapshot and reject escaping links. A claim command
or plugin runs only when the manifest declares its exact argument array.

A project-scoped impact plan materializes only the selected repository subtree from each immutable
ref, plus transitive repository-internal targets required by symlinks in that subtree. Absolute or
escaping symlinks fail. Read the receipt's `project` field before reusing an `impact: none`
conclusion: omitted sibling projects and materialized symlink targets are not covered surfaces.

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

Live evaluation writes `clean-docs.provider-run.v1` before it invokes a command provider. The
pre-invocation record binds the immutable commit when available, worktree bytes, corpus, prompt,
scorer, provider configuration, prompt byte count, and bounded process deadline. Completion adds
the response and post-worktree digests. Failure keeps the input record, and an unexpected
repository byte change becomes a conflict. Existing command fixtures use a 120-second compatibility
default; an explicit `timeout_seconds` value from one to 3,600 seconds becomes part of provider
identity.

## Current non-goals

clean-docs does not:

- infer or authorize product goals, audience priorities, non-goals, or safety policy;
- decide that every detected symbol deserves reader documentation;
- treat a ranked source-claim candidate as proof or rewrite unrelated prose after a source change;
- treat mutation sensitivity as semantic correctness or relationship authority;
- infer review relationships or treat source-target co-change as semantic correctness;
- use model judgment as a required gate;
- provide operating-system or network isolation;
- maintain a hosted service, account system, or runtime dashboard;
- send feedback unless an operator explicitly enabled a sink and invoked `feedback flush`;
- claim that generated prose reaches the quality of a skilled human writer.

## Compatibility

The 1.x line preserves manifest version `1`, plugin API version `1`, published machine schemas, and
stable command meanings. Minor releases may add optional fields. An incompatible manifest exits
`2` before extraction, and a removed stable surface requires a major release.

Repository-overview receipts created before the current digest algorithm remain valid while their
catalog surface is unchanged. A later surface change rewrites the region with the current
versioned extractor. Impact plans name their producer because a plan conclusion is only
reproducible with the same planner semantics.

Use the [install guide](docs/INSTALL.md) for package and artifact lifecycle tasks. The
[support guide](docs/SUPPORT.md) owns CI pinning, corpus adoption, receipts, and diagnostics.
