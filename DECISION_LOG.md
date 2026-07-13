# clean-docs decision log

This file records consequential product and implementation choices, their evidence, and their
reversibility.

<!-- clean-docs:allow doc-length reason="Product decisions stay in one chronological canonical log" -->

## 1. Define the reader-facing surface by the repo's own index, not by filename alone (2026-07-12)

Context: the corpus rule "process artifacts belong off the reader-facing surface" needs a
definition of that surface. Options: (a) treat every tracked `.md` as reader-facing and archive
anything whose name matches a process pattern; (b) treat the index that `docs/README.md` and
`LIMITS.md` build as the surface, and archive only orphaned process docs. Chose (b): the repo
already curates a Start Here / Decisive proof / Core References / Evidence archive layout and
cites specific reports as claim-evidence, so honoring that curation is more truthful than a
filename sweep, and it prevents archiving a report that `LIMITS.md` depends on. Reversible: the
kept-vs-archived split is a list in NOTES; any file can be re-archived or restored with one `git
mv`.

## 2. Archive into `docs/archive/`, conforming to the existing convention, not a new top-level `archive/` (2026-07-12)

Context: the work order suggested "an `archive/` outside the doc tree." ultra-csm already has a
populated `docs/archive/` (51 historical program reports). Options: (a) create a top-level
`archive/` as the work order literally says; (b) extend the existing `docs/archive/`. Chose (b):
a second archive home would compete with the first and violate the one-canonical-home rule the
standard teaches. Deviation from the literal instruction is deliberate and noted. Reversible:
the moves are renames; relocating the whole archive later is another `git mv`.

## 3. Archive superseded prompt versions rather than special-case them in the linter (2026-07-12)

Context: `agent1_slot_b_reason_draft_v1/v2/v3` are near-duplicates of `v4` and of each other
(~38 near-dup findings). Code loads only `v4`. Options: (a) add a linter exception for versioned
prompt files; (b) archive the superseded versions so only the canonical one remains. Chose (b):
older versions are history that git holds, and keeping one canonical version is the exact fix the
one-canonical-home rule prescribes. No linter change was needed. Reversible: `git mv` back if a
version is ever needed on the surface.

## 4. Linter tune -- exclude an `archive/` path segment from the directory scan (2026-07-12)

Context: after the moves, 196 findings sat inside `docs/archive/`, flagged as "on the
reader-facing surface." An archive is off-surface by construction. Options: (a) leave it and
justify 196 findings; (b) skip `archive/` in the scan. Chose (b): the linter's job is the reader
surface, and archived history is not it; an explicit single-file target still lints so an archived
doc can be inspected on demand. Evidence: 51 already-archived program reports were flagged before
any of my moves. Reversible: one regex, `ARCHIVE_RE`, gates it.

## 5. Linter tune -- drop `IF/THEN` from HARNESS_RE (2026-07-12)

Context: the only audience findings on genuine docs (`AGENT_PROFILE.md` x3,
`TENANT_LOOPWAY_BIBLE.md` x4) were driven entirely by `IF/THEN`. In this repo `IF/THEN` names a
decision-record format; it appears in citations ("recorded in `PROGRAM_REPORT_14`'s IF/THEN") and
as a metrics-table column, not in agent-address prose. Options: (a) keep it and justify the two
docs; (b) drop the token. Chose (b): the strong agent-address signals ("next executor", "pick up
this branch", "worktree", "STOP condition") remain, so dropping one generic-looking token removes
false positives without hiding a real agent-addressed doc. Reversible: one term in one regex.

## 6. Linter tune -- drop `byte-identical` from PROVENANCE_RE (2026-07-12)

Context: `byte-identical` flagged `LIVE_INTEGRATION_FINDINGS.md:392` ("per-arc round-trip
byte-identical after CRLF normalization") and `AGENT_PROFILE.md:17,93` (a `make`-target `PASS:`
message and meta-discussion of the phrase). Those are technical fidelity claims, not authoring
receipts. Options: (a) keep it and justify; (b) drop it. Chose (b): round-trip byte-equality is a
real content claim about data as often as it is a receipt, and the `(Program|Wave|Harvest N)`
tags plus "verified after authoring" carry the provenance-as-canon signal. Reversible: one term.

## 7. Record three gaps as judgment-only in the standard, do not fake a mechanical check (2026-07-12)

Context: three real distinctions the run exposed cannot be mechanized safely. An executed plan
vs a live plan differs by a status line, not a name (`RESEED_PLAN` "EXECUTED" vs `EVAL_PLAN`
"active"). A doc about agent operation vs a doc for a future agent differs by who the second
person is, not by vocabulary density. "Each section leads with its takeaway" has no token
signature. Options: (a) add brittle regexes; (b) record them as instruction-only in the
standard's honest seam and name where an LLM-judge pass slots in. Chose (b): a judge-by-pattern
check for a judgment call misfires in both directions, the failure mode this system was built to
avoid. Reversible: prose in `STANDARD.md` section 6.

## 8. Emit interoperable stepwise skills via an edge adapter, not an engine change (2026-07-13)

Context: an interoperable distribution target requires a stepwise skill format. Options: (a)
teach the engine that format; (b) keep one native model and project it through an edge adapter.
Chose (b). `src/clean_docs/emit/stepwise.py` reads the manifest and writes `config.yaml` plus
ordered reference steps chained by `next_step`. The package names the repository's bound docs
and carries clean-docs' audit, repair, and verify workflow, so it is a projection instead of a
static clone. Other projection formats can remain sibling adapters over the same model. The
`test_emit_stepwise` E2E proves schema shape, stable reruns, manifest grounding, navigation, and
workflow execution in a temporary repository. A target-specific build, security scan, or server
integration remains outside this proof. Reversible: the adapter is isolated under `emit/`;
deleting it leaves the engine untouched.

## 9. Separate command projections from content indexes (2026-07-13)

Context: the stepwise package carries clean-docs' maintenance commands, while an agent-readable
content index must point at the repository documentation itself. Treating one payload as the
other would make a format-correct artifact serve the wrong reader task. Chose two explicit
projections. `emit stepwise-skill` packages the audit, repair, and verify workflow.
`emit llms-txt` indexes manifest-bound documents with binding identifiers and content digests.
The latter changes deterministically when a bound document or binding changes; a later projection
gate will make committing that change mandatory. Reversible: both implementations are isolated
under `emit/` and share only the native manifest model.

## 10. Keep the product local-first and make the demonstration static (2026-07-13)

Context: the deterministic CLI, pre-commit hook, CI action, and projections already cover the
maintenance workflow. A hosted system would add runtime trust, storage, account, and
operations surfaces without improving source binding or gate correctness. Chose to keep those
surfaces out of the product. The only web output is a static demonstration generated from
recorded fixture evidence, with no backend, credentials, runtime network dependency, or CLI
telemetry. Machine-readable outcome receipts stay local or in CI artifacts. Reversible: a future
consumer can process the same receipts without changing the core or the local default.

## 11. Freeze the Version 0.1 runtime and ordering contracts (2026-07-13)

Context: a release cannot claim reproducibility while its runtime and ordering behavior remain
open. Chose CPython 3.10 through 3.14 on Linux and macOS, with every pair in required CI. Static
Python evidence uses the standard-library syntax tree. Generated tables and lists preserve
evidence order, while path evidence sorts lexicographically. `derive` remains preview-only unless
`--write` is present. A static micro-repository check has a five-second ceiling; allowlisted
commands retain their declared timeouts. Reversible: later releases may add runtimes or platforms
without changing the Version 0.1 behavior for existing repositories.

## 12. Make bootstrap a reviewable content plan with an atomic write gate (2026-07-13)

Context: repository initialization must write by default while keeping its factual authority
inspectable and deterministic. Chose one content plan that records normalized evidence, content
digests, exact diffs, archive moves, and unsupported-adapter gaps before any mutation. `--dry-run`
returns that same plan without writing. The default path rejects gaps, applies the planned moves
and writes, then requires binding and policy checks to pass. Existing manifests are never replaced
implicitly. Reversible: the plan schema isolates bootstrap decisions from the binding engine, so a
later information-architecture planner can add operations without weakening the write gate.

## 13. Restrict model phrasing to grounded templates (2026-07-13)

Context: free-form model prose cannot be factual authority, but repository onboarding still needs
an optional phrasing seam. Chose a provider protocol whose response can only map known evidence
identifiers to compatible prose templates. Deterministic code validates the mapping and renders
the sentence. Unknown facts, arbitrary fields, duplicate mappings, and incompatible templates
fail before writes. Prompts are deterministic, secret-redacted, and stripped of repository
instructions; required checks never consume provider output. Reversible: additional templates can
be added with explicit compatibility tests without broadening the provider's authority.

## 14. Treat bootstrap writes and moves as one transaction (2026-07-13)

Context: a pinned repository failed policy checks only after bootstrap had moved process documents
and written its baseline. Leaving those changes behind would make a failed command unsafe. Chose
to snapshot every write target, track each completed move, and restore both files and directories
when binding or policy verification fails. The same dogfood also consolidated the process-name
rule, preserved the repository's actual README casing, and removed three inventory false
positives before the Python and TypeScript receipts were accepted. Reversible: the transaction is
contained in bootstrap application and does not change the binding engine.

## 15. Make coverage exceptions strict and explainable (2026-07-13)

Context: inventory already labeled surfaces bound, ignored, or standard-gap, but malformed ignore
files were silently discarded and readers could not resolve a finding identifier to its evidence
and repair. Chose a versioned ignore schema with known IDs, unique entries, and specific reasons.
`explain` now reports required policy repairs separately from non-blocking coverage states and
includes adapter, source, locator, and digest evidence. Invalid policy exits as configuration
error instead of changing coverage implicitly. Reversible: new policy fields require a schema
version change; existing valid reasoned ignores retain their meaning.

## 16. Compare normalized surfaces across refs before filtering by changed files (2026-07-13)

Context: file diffs alone cannot tell whether a change created a public surface or only modified
private implementation. Chose to inventory immutable base and head snapshots, compare stable
surface identifiers, and evaluate deterministic bindings at head. Existing binding drift is a
required result; newly added unbound surface is a separate coverage gap; reasoned ignores remain
visible. Finding identity hashes the rule, document, source, and locator, and the same identifier
is carried into SARIF fingerprints. Reversible: later dependency filtering and caching can reduce
work without changing the normalized report contract.

## 17. Cache immutable inventory outside the worktree (2026-07-13)

Context: changed checks repeatedly inventory the same base ref, but cache metadata must not alter
repository content or normalized results. Chose content-addressed inventory entries under the Git
metadata directory, keyed by extractor version, project parameters, and commit SHA. Cache hit and
miss diagnostics stay outside the machine-readable report. A new head reuses base inventory and
invalidates head inventory; cached and uncached reports must be byte-identical after normalized
serialization. The reusable action retains read-only permissions and publishes escaped workflow
annotations, a step summary, JSON, and SARIF artifacts. Reversible: deleting the cache directory
only removes an optimization.

## 18. Treat generated context as a verified projection, not a second corpus (2026-07-13)

Context: a task bundle must carry exact canonical pages, but linting that copy as another
reader-facing page would report intentional duplication and invite edits in the wrong file.
Chose a strict projection contract in the manifest. Each bundle names bound source documents,
records `WORKTREE` and a corpus digest, links back to every canonical page, and is regenerated by
`project`. `check` compares the generated bytes and verifies local links and anchors. Generated
Markdown under `.clean-docs` is excluded from canonical corpus hygiene because projection checks
own it. Working-tree output does not embed `HEAD`: committing that value would change `HEAD` and
make the projection stale again. Immutable refs will be recorded only when projecting an
immutable snapshot. Reversible: projection output paths and source selection remain manifest
data, while removing the projection leaves the canonical corpus unchanged.

## 19. Separate provider execution from deterministic task scoring (2026-07-13)

Context: an agent round trip has two different claims: a specific provider produced a response,
and a deterministic scorer accepted or rejected its observable output. Combining them would make
offline regression tests depend on a network or imply that one recorded result generalizes to
other models. Chose replay as the default. Recorded responses are scored without provider
execution; live command adapters require `--mode live` and a record directory. Reports label live
outcomes model-specific, split human and agent scores from hygiene findings, and record corpus,
prompt, response, model, scorer, and result digests in a deduplicated history. Human command tasks
must name an allowlisted command and an excerpt present in their supplied docs. Reversible: new
provider adapters can implement the same response protocol without entering deterministic gates.

## 20. Generate one static demonstration from recorded evidence (2026-07-13)

Context: the product needs a showable drift workflow, but a web application would add state,
accounts, storage, and runtime trust without improving the local gate. Chose one HTML projection
from a strict three-state evidence record. The recorder runs a temporary repository through
current, drifted, repaired, and verified states; `project` renders those exact commands and
outputs. The renderer requires task-first reader slots, one heading hierarchy, labeled landmarks,
a skip link, local fragment integrity, and no scripts or external runtime assets. A Pages workflow
uploads only the generated file after `project --check`; the CLI remains local and emits no
telemetry. Desktop and 390-pixel viewport checks caught and fixed digest overflow before publish.
Reversible: deleting the demo projection and deployment workflow leaves every CLI and evaluation
contract intact.

## 21. Resolve allowlisted Python commands against the running artifact (2026-07-13)

Context: the release-artifact gate passed audit and projection checks but its human task failed.
The fixture invoked `python3`, which selected the runner's ambient interpreter instead of the
wheel's interpreter. Chose an explicit `{python}` executable token for allowlisted commands and
live provider adapters. clean-docs resolves the token to `sys.executable`; literal executables
keep their existing meaning, and the token is rejected outside the first argument. The doctor,
command extractor, and task scorer use the same resolver. A clean wheel now evaluates the same
artifact that launched the command. Reversible: replacing the token with a literal executable
restores ordinary process lookup without changing the manifest schema.

## 22. Keep release facts separate from narrative phrasing (2026-07-13)

Context: release notes need useful prose, but a generated explanation cannot become authority for
what changed. Chose a typed delta over normalized inventory evidence extracted independently at
two immutable refs. Added, removed, and changed records carry source, locator, adapter, and
evidence digests; Markdown and JSON render from that record. Optional recorded narrative must
mirror every deterministic field and citation. One omission, contradiction, duplicate, policy
violation, or missing citation withholds the entire narrative while leaving the factual section
unchanged. Reversible: removing narrative validation leaves the offline release skeleton intact.

## 23. Run extensions as strict processes against disposable snapshots (2026-07-13)

Context: ecosystem adapters must evolve without importing repository or third-party plugin code
into the core process. Chose one API-versioned JSON protocol for extractor, discoverer, renderer,
and policy interfaces. Each invocation receives a disposable repository copy, temporary home,
minimal environment, timeout, and output cap. Symbolic links fail before execution; filesystem
writes are discarded with the copy. Compatibility is validated before a command runs, and core
code owns evidence identity, digests, and coverage state. Manifest migration remains separate:
version 0 to 1 writes an exact backup and supports rollback to the original bytes. Reversible:
removing a plugin declaration leaves built-in adapters and manifest v1 behavior unchanged.

## 24. Reject extension evidence identity collisions (2026-07-13)

Context: an extension could otherwise emit the same kind, source, and locator as first-party or
another extension's evidence, causing a dictionary merge to replace the earlier record. Chose to
make duplicate extension IDs and collisions with first-party inventory hard extraction failures.
Inventory, changed checks, and release comparison use the same merge rule, so no output path can
silently pick a different authority. Reversible: a future namespaced identity schema can replace
the collision rule through a versioned plugin API migration.

## 25. Apply one disposable-process boundary to commands and plugins (2026-07-13)

Context: allowlisting a command defines what may run, but it does not constrain where that process
reads or writes. Chose one process runner for declared commands and plugins. It rejects repository
symlinks, copies the selected snapshot, supplies a temporary home and minimal environment, passes
literal arguments without a shell, and enforces timeout, combined-output, and secret-output limits.
Writes to the disposable copy are discarded. This is process isolation, not an operating-system or
network sandbox, and the public security model says so. Reversible: a stronger platform sandbox can
implement the same bounded result contract.

## 26. Keep outcome and diagnostic receipts local and content-safe (2026-07-13)

Context: continuous use needs evidence that drift was caught and enough runtime context to diagnose
failures, but CLI telemetry would weaken the trust boundary. Chose deterministic local JSON
receipts. `verify` records audit, binding, projection, and changed-check outcomes; `benchmark`
records P95 time and process memory; `doctor --bundle` records versions, counts, plugin identifiers,
and checks. Each declares zero network requests. Diagnostic output excludes environment variables,
credentials, repository contents, and command arguments. Reversible: users can aggregate files in
their own systems without changing local execution.

## 27. Protect bootstrap projections in the generated manifest (2026-07-13)

Context: `init` wrote `llms.txt` but did not declare that file as a checked projection, so the first
generated repository could drift immediately after reaching a passing baseline. Chose to place the
projection declaration in the generated manifest and verify both bindings and projections before
bootstrap completes. Reversible: another declared output can replace `llms.txt` without creating an
unowned generated file.

## 28. Publish reproducible release evidence with signed attestations (2026-07-13)

Context: a reproducible wheel proves byte stability locally but does not identify the public build
that produced a downloaded asset or disclose its dependency claims. Chose deterministic SPDX 2.3
SBOM generation from wheel metadata, checksums covering the wheel and SBOM, and GitHub artifact
attestations for provenance and the SBOM. Official workflow actions are pinned to immutable commits.
The release gate also installs the prior release, upgrades, rolls back, upgrades again, and uninstalls
the candidate. Reversible: another signing service can attest the same wheel digest and SBOM bytes.
