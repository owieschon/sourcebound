# clean-docs decision log

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this log when a current clean-docs behavior needs its design rationale or reversal path. It keeps consequential choices out of task docs so maintainers can change a decision without mistaking old process history for product truth.
<!-- clean-docs:end purpose -->

**[Read the newest decision](#31-hash-python-source-evidence-instead-of-runtime-ast-serialization-2026-07-13)**.

Each entry records its context, choice, consequence, and reversal path as the design receipt.

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

## 29. Compile the writing personality and enforce a BLUF purpose contract (2026-07-13)

Context: the authored standard described a specific voice, but runtime policy enforced only booster
words and audit did not invoke that policy. The README exposed the gap as a dense capability list.
Chose to compile the voice into structured generation data and require each reader-facing Markdown
page to open with one marked purpose contract that names applicability, problem, and outcome.
Deterministic checks own presence, position, prose shape, and title-restatement rejection; human or
agent judgment owns truth and scope. Bootstrap preserves an existing author opener inside markers.
Source-derived Markdown fragments preserve paragraph boundaries so regeneration cannot collapse the
README back into brochure prose. Reversible: a future pack version can change the markers or rubric
through an explicit migration without weakening current repositories silently.

## 30. Bind the README purpose contract to independent-reader evidence (2026-07-13)

Context: Version 1.0 required a new reader to identify the README's applicability, problem, and
resulting capability, but the release rubric still contained only the four tasks that predated
the purpose contract. A stable receipt could therefore pass without testing the writing behavior
that prompted the rule. Added a fifth exact task that limits the reader to the first body block
and records the three contract slots as content-addressed evidence. The acceptance suite asserts
the task ID, instruction, and passing rubric. Internal rehearsal still cannot substitute for an
independent human and agent result. Reversible: a later rubric version can replace the task only
with an independently tried measure of the same reader outcome.

## 31. Hash Python source evidence instead of runtime AST serialization (2026-07-13)

Context: the RC8 pilot gate derived one repository-overview digest under Python 3.12 while local
repair under Python 3.14 derived another from the same Git tree. `ast.dump` includes fields added
between CPython releases, so the evidence hash encoded the interpreter rather than only the source.
Changed Python inventory evidence to hash the exact source segments selected by the static AST
walk. The parser still decides which symbols, commands, tools, and settings exist, while their
digests now remain identical across supported runtimes. A fixed digest assertion and a direct
3.12-versus-3.14 replay cover the failure. Reversible: a future versioned semantic encoding can
replace source segments after proving identical bytes on every supported runtime.

## 32. Separate impact fingerprints from established inventory receipts (2026-07-18)

Context: interface-level fingerprints let an impact plan ignore a function-body refactor and catch
a public default change, but replacing the existing inventory digest invalidated repository
overviews whose rendered rows had not changed. Chose a planner-owned semantic fingerprint for
Python and TypeScript interfaces while preserving the published inventory bytes. Impact receipts
also bind the clean-docs producer version. Repository-overview evaluation accepts both the legacy
item-digest receipt and the current rendered-surface receipt until the catalog changes; a real
surface change migrates the region to the current extractor. Tests prove four cases: changed
bodies stay out, changed signatures enter, old receipts pass, and renamed symbols fail. Reversible:
a future manifest migration can retire legacy receipt acceptance after adopted repositories have
rewritten their regions.

## 33. Let only public inventory kinds create changed-surface gaps (2026-07-18)

Context: document links use their line number as an inventory locator. Moving an unchanged link
therefore creates one removed record and one added record, and the changed check had labeled the
added record a new public surface. Chose one shared set of public kinds for the changed gate and
impact planner. Documents, links, and tests remain enumerated evidence, but only APIs, commands,
configuration, packages, runtimes, and schemas can create a public-surface gap. The planner emits
semantic events from the same set, so prose movement cannot invent a contract change. Tests move a
link inside a bound document and require both the stable gate and impact plan to stay clear.
Reversible: a new public kind can join the shared set when an adapter defines its contract.

## 34. Keep machine paths in test fixtures visible without giving them veto power (2026-07-18)

Context: an untouched TypeScript monorepo used literal home paths to test `file://` handling and
path normalization. Repository integrity enforcement would have blocked adoption until those
valid tests were rewritten or baselined. Chose to keep `local-path-residue` records from recognized
test paths as advisories in both assessment and adopted modes. The same rule still blocks on
product source, documents, and lockfiles. This changes severity, not detection, so an operator can
still inspect the exact path and line. A regression fixture puts a literal home path in a tracked
TypeScript test and requires an adopted audit to report it only as an advisory. Reversible: a
repository can exclude or rewrite the fixture, while future path roles can refine the classifier.

## 35. Preserve safe internal symlinks only in read-only snapshots (2026-07-18)

Context: a TypeScript monorepo shares package-manager configuration through tracked relative
symlinks. The immutable snapshot reader rejected every symlink, so changed checks and impact plans
could not inspect an otherwise supported repository. Chose to materialize a symlink only when its
target is relative and normalizes inside the snapshot root. Absolute links, escaping links, and tar
hardlinks still fail before extraction. Executable commands and plugins keep their stricter
no-symlink boundary because they run third-party processes. Tests prove an internal configuration
link reads the expected bytes and a parent-escaping link fails. Reversible: the static reader can
copy internal targets instead if a supported platform cannot preserve symlinks.

## 36. Fingerprint TypeScript interface bodies without hashing implementation bodies (2026-07-18)

Context: a real SDK feature added an option to exported interfaces, but the impact planner hashed
only each declaration line and reported no impact. Chose balanced static fingerprints for
interfaces, object-shaped type aliases, and enums. The scanner ignores braces inside comments and
quoted strings. Functions, constants, and classes keep their declaration-only fingerprint, so an
implementation edit does not automatically become documentation work. The existing TypeScript
acceptance case now adds an interface member and requires a public-contract event. Reversible: a
parser-backed adapter can replace this bounded scanner while preserving the event schema.

## 37. Read changed interfaces from immutable blobs instead of full archives (2026-07-18)

Context: a four-file feature in a 3,360-file monorepo materialized the complete repository at both
refs solely to fingerprint four interfaces. The diff was not the cost. Chose direct immutable blob
reads for only the changed Python, TypeScript, and JavaScript paths. Inventory still scans each
repository snapshot because it owns additions and removals across the catalog. This removed two
redundant archives without changing the plan digest, but the warm end-to-end run remained about 21
seconds because changed-check and graph evaluation still materialize separate head snapshots.
Further snapshot sharing remains measured follow-up work. Reversible: a batch Git reader can replace
the per-path calls without changing plan semantics.

## 38. Bootstrap only the root orientation page into projected context (2026-07-18)

Context: filename and depth ranking chose eight supposedly canonical pages in a large monorepo,
including compliance and example READMEs while omitting most package documentation. That ordering
was not evidence of repository purpose. Chose to bootstrap `llms.txt` with only the root README and
the generated bound catalog. Existing documents remain untouched, and operators can add exact
manifest includes after deciding which pages carry canonical context. The mature-monorepo test now
proves architecture records and ADRs stay out until declared. Reversible: a repository can add any
document through the existing projection contract without changing bootstrap code.

## 39. Canonicalize empty AST fields in impact fingerprints (2026-07-18)

Context: the same committed impact plan produced different public-symbol digests under Python 3.12
and 3.14. Python 3.14 omits empty AST fields by default, while earlier supported runtimes include
them. Chose one canonical representation that always includes empty fields when the runtime exposes
that switch and uses the equivalent earlier-runtime default otherwise. This preserves the semantic
fingerprint while making one clean-docs version produce the same receipt across supported Python
runtimes. The Version 1.2A registry pins that behavior. The release gate compares complete receipts
from Python 3.12 and 3.14. Reversible: a parser-independent format can replace this representation
after reproducing the same public-change boundaries.

## 40. Share one immutable head snapshot across impact-plan stages (2026-07-18)

Context: the planner ran changed checks, loaded the manifest, checked projected files, and built its
graph against the same committed head, but read that commit into a temporary tree twice. Chose one
validated, read-only head snapshot and returned its base and head inventories with the internal
changed report. The public changed-check contract stays unchanged. A test counts one snapshot for
each ref. Before the release version changed, complete plan receipts remained byte-identical to
Version 1.2.0rc1.
On a 3,364-file public repository, the uncached path fell from 65.89 seconds to 45.36 seconds; a
same-run cached comparison fell from 16.66 seconds to 15.48 seconds. Reusing inventory evidence
inside repository-overview bindings remains separate measured work. Reversible: callers can return
to independent snapshot contexts without changing receipt semantics.

## 41. Publish releases as create-or-verify transactions (2026-07-18)

Context: the Version 1.2.0rc2 tag workflow built and attested valid artifacts, then failed because a
manual publisher had already created the same-tag release. Chose one create-or-verify publisher.
An absent release is created once. An existing release succeeds only after its tag, prerelease
state, complete asset set, downloaded byte digests, provenance, and SBOM attestations match. A
difference is a conflict, and the publisher leaves remote bytes untouched. The workflow writes its
publication receipt after verification. Tests cover absent, identical, raced-identical, and
conflicting states. Reversible: a different release host can implement the same state comparison
without changing the artifact contract.

## 42. Separate command-output assurance from prose and network assurance (2026-07-18)

Context: legacy `type: claim` bindings checked allowlisted command JSON against a configured value
but never read the prose under their document anchor. Outcome, diagnostic, and performance
receipts also printed zero network requests without observing traffic. Chose the public name
command pin while preserving the legacy manifest spelling. Binding and outcome receipts now state
that command output was checked and anchored prose was not. Receipts at schema v2 say clean-docs
neither blocks nor observes network traffic. Manifest version 2 removes the
decorative `network` key; version 1 remains readable and migratable. Pull-request checks select
static-only execution, report skipped commands and plugins, and fail when a change affects one of
those skipped relationships. Reversible: trusted default-branch checks can still run declared
processes, but no mode restores the unmeasured request count or the prose-assurance implication.

## 43. Make adoption debt stable by identity, not by line (2026-07-18)

Context: accepted audit debt included its line number in the fingerprint. Inserting prose above an
unchanged broken link therefore created one new finding and one stale baseline entry. Chose a
version 2 multiset identity from path, rule, normalized offending content, section anchor, and
duplicate ordinal. The line remains a display hint. Version 1 baselines remain readable, and an
explicit baseline update migrates them. The same correction pass closes four adjacent false
states: path globs with no matches now fail extraction, an opening frontmatter delimiter needs a
close, placeholder links are exempt only in templates and agent procedures, and changed MDX is
reported as unsupported unknown impact. Reversible: the version 1 reader remains available, but
new baselines and impact receipts keep the stricter identities and boundaries.

## 44. Persist provider intent before invocation and compile context by evidence (2026-07-19)

Context: one feasibility run passed a 24 KB packet of mixed source and documentation excerpts to
the existing command provider. It reached the 120-second boundary without a response. The runner
had computed its pre-run worktree digest but planned to write the receipt only after completion, so
the timeout discarded the value needed to reconcile the attempt. Chose two narrow primitives.
Live evaluation now writes a content-addressed provider-run record before launch and preserves
failure or worktree-conflict state. A separate model-free context compiler selects typed source
ranges under an explicit byte budget, records exclusions, and grants instruction authority only to
accepted policy. It uses no vector store or semantic retriever. Reversible: recorded evaluation and
unbounded, manually prepared context remain readable; callers can ignore the new compiler and
provider-run receipt without changing deterministic checks.

## 45. Match Python's effective mapping keys (2026-07-19)

Context: a demonstrated fixture with two occurrences of the same string key produced duplicate
identifier evidence and a raw entry count, although Python keeps only the last value for that key.
That mismatch could report drift against documentation listing the effective mapping once. Chose
to deduplicate static string-key evidence and count distinct, statically evaluable dictionary or
set keys. Mappings with unpacked or non-literal keys remain uncounted because their effective size
is not available without execution. Reversible: accepted facts keep the same locators and schemas;
only previously duplicated or unknowable dictionary and set evidence changes.

## 46. Rank relationship evidence before drift status (2026-07-19)

Context: a frozen external corpus produced 330 assessment candidates. Deep sibling paths and
generic file tokens gave unrelated pairs high scores, while the 100-item display cap hid every
current pair. Chose conservative ownership signals: counts need the same directory or a meaningful
file-stem match; identifier tables may also use an exact heading-to-locator match. Common path depth
is only a tie-breaker, relationship rank precedes value equality, and the report states its full
population and truncation. Reversible: accepted relationships and enforcement do not use discovery
ranking; callers may ignore the additive population fields.

## 47. Make provider deadlines part of the run contract (2026-07-19)

Context: a second frozen external calibration reached the command provider's hard-coded
120-second boundary without a response. The pre-invocation receipt preserved the failed attempt and
proved the target bytes had not changed, but neither the provider identity nor the receipt exposed
the deadline, and the receipt did not state the prompt size that consumed it. Chose a bounded
`timeout_seconds` command-adapter field from one to 3,600 seconds, with the prior 120-second value as
the compatibility default. The deadline participates in provider identity. Pre-invocation receipts
state it and the prompt byte count before execution. A timeout remains a failed provider attempt,
never a content-quality result. Reversible: existing fixtures retain their prior deadline; callers
can remove an explicit value to return to it without changing scorer semantics.

## 48. Treat mutation-red as dependency evidence, not semantic authority (2026-07-19)

Context: a frozen private discrimination test made both correct source relationships red after an
independent static mutation. It also made two wrong, shape-compatible relationships
red. Chose a narrow read-only sensitivity primitive. The provider proposal and scorer-controlled
fact stay in separate, digested inputs; clean-docs reads committed blobs, generates one syntax-safe
mutation in a disposable copy, and reports `sensitive`, `insensitive`, `invalid`, or `unsupported`.
Every receipt sets `semantic_relationship_authorized` to false. The `mutation-red` scorer calls the
same code; a red result cannot accept the link. Reversible: removing the command and scorer leaves
configured source-claim enforcement unchanged; no manifest or published gate depends on this
additive receipt.

## 49. Make pull-request readiness one coverage-stating receipt (2026-07-19)

Context: the reusable gate exposed separate audit, binding, changed-surface, and action receipts.
Each result was accurate within its own scope, but a caller had to reconcile them and could present
sparse coverage as repository-wide proof. Chose one static-only pull-request verdict composed from
the existing library results. It pins the checked-out head, reports each mechanism and coverage
class separately, carries stable JSON and SARIF finding IDs, and names what it does not certify.
Unsupported public change and affected skipped execution become `unknown`; neither can exit zero.
A caller may attach a sensitivity receipt, so clean-docs verifies its commit and mutation plan.
That attached receipt cannot alter the state or authorize the relationship. Reversible: the
independent audit, check, plan, verify, and binding-sensitivity schemas remain available, and
removing the command changes no manifest or repair behavior.

## 50. Keep pull-request delivery static and package verification separately (2026-07-19)

Context: the reusable workflow recomputed audit, binding, and changed-surface results, then built a
second action-level decision. The generic maintenance skill could write documentation, and its
apparently read-only inventory command could still start a declared discoverer plugin. Chose one
static verdict as the workflow authority. SARIF is rendered from those recorded JSON bytes, the
artifact receipt hashes every transport file, and the final job validates the verdict digest and
file hashes before using its state. The workflow exposes no execution switch. A separate
verification skill permits only static inventory, claims, impact, verdict, and independently frozen
sensitivity commands; `inventory --no-exec` reports skipped plugin IDs. Release CI runs the exact
README quickstart from the wheel outside the source checkout on Linux and macOS. Reversible:
callers can pin the prior workflow or remove the skill without changing CLI checks, manifests, or
repair behavior. The workflow also starts Python in isolated mode and writes receipts outside the
checkout, preventing fork-controlled import hooks or symlinks from redirecting trusted evidence;
static pull-request execution remains the security floor.
