# DECISION_LOG: consequential choices in the doc-standard harden-and-prove pass

Each entry states the context, the options, the choice and why, and how reversible it is. This
is a changelog surface, so it carries dates and program provenance on purpose.

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
