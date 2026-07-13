# NOTES: working log for the doc-standard harden-and-prove pass

This file records the current-state read, the STANDARD.md self-check, the ultra-csm triage,
and a per-finding justification for everything the tuned linter still reports. Decisions with
alternatives live in `DECISION_LOG.md`; the reader-facing summary lives in `REPORT.md`.

## Phase 0: current state

The system is a three-tier documentation standard plus two detectors. Tier 1 is a per-write
gate (`quality-gate.py`, PreToolUse) that blocks sentence-level slop before a file exists. Tier
3 is a corpus linter (`doc-hygiene.py`) that finds process artifacts, agent-addressed docs,
provenance-as-canon, over-length docs and sections, and near-duplicate paragraphs across a
tracked doc tree. The packaged project standard (`STANDARD.md`) is the
single reference both detectors enforce, and the scrub skill runs the corpus linter as a
companion in the pre-publish sweep. Both detectors are detect-only: they report, a human fixes.

Baseline before any change: `doc-hygiene.py` reported 280 findings on ultra-csm
(surface=91, section-length=93, near-dup=54, doc-length=22, provenance=11, audience=7,
restatement=2). Run against itself the standard reported one finding: 224 lines over the
120-line one-file threshold.

## Phase 1: STANDARD.md self-check (section 7, walked by hand)

Result: pass, with one finding justified rather than removed.

- Code blocks have prose lead-ins ending in a colon: pass (the escalation-ladder block and the
  MCP block both lead in).
- No table encodes precedence or ordering: pass (the medium-by-verb table is a lookup).
- Left columns are bare tokens; choose-among columns are reader questions: pass.
- Every "don't" pairs with an "instead": pass.
- Callouts are semantic, none carries a first explanation: pass (the callout rules are prose).
- Placeholders and real values never share a line; language tags correct: pass.
- The page names its one governing constraint early: pass ("choose the medium by what the
  reader is doing at that sentence").
- No booster adjectives: pass (the two occurrences name the banned set as negative examples and
  carry a `slop-ok` pragma).
- One-claim sentences, system as actor, imperative actions: pass.
- Sections end by linking outward; version notes inline: pass.
- No process artifact on the surface; audience is a reader: pass (the standard is a reference).
- No fact restated across siblings; provenance in a changelog: pass.
- Each section leads with its takeaway: pass.
- Docs over 120 lines and sections over 40 lines justify or split: **justified, not removed.**
  The standard is 229 lines. Its first paragraph now states why it stays one file: the three
  tiers are read as one system, and splitting them would break the one-canonical-home rule the
  doc itself teaches. This is the sanctioned "justify staying whole" outcome, not a failure.

Fixes applied during the walk: removed all three uses of the prohibited compound phrase (the
one meaning "does the essential work") and named the actor instead -- a language tag now "sets
the reader's action", and the single page constraint is "governing". Normalized 24 em dashes to
the ASCII double-hyphen convention Owen's own scripts use. Added the honest-seam subsection in
section 6 (the three judgment-only checks the linter cannot mechanize).

## Phase 2: ultra-csm triage

The reader-facing surface is defined by the repo's own index: `docs/README.md` curates a Start
Here / Decisive proof / Core References / Evidence archive layout, and `LIMITS.md` links
specific reports as evidence for specific claims. A doc reachable from that index is
reader-facing; an orphaned process doc is exhaust. That distinction, not the filename alone,
drove the triage.

**Real findings, fixed by hand (documentation only, on `docs/hygiene-pass-1`):**

- 30 orphaned process artifacts relocated into `docs/archive/` (git `mv`, history preserved):
  `BLOCKED*.md`, `STATUS.md`, every `EXECUTOR_HANDOFF*`, `CURRENT_EXECUTOR_HANDOFF`,
  `*_DISPATCH`, `MP_D2_WAVE*_RECEIPT`, `DEMO_EXECUTION_PLAN`, `P3_EXECUTION_PLAN`,
  `FOREIGN_CORPUS_FINDINGS`, `SALESFORCE_ONESHOT_FINDINGS`, `QUALITY_LABELING_PROTOCOL`,
  `RETRO_PROPOSALS_2026-07`, `WEEK1_PROTOCOL`, the bare `PROGRAM_REPORT` and the reports LIMITS
  does not cite (`_40`, `_54`, `_66`, `_71`), plus two executed plans
  (`PHASE_2_3_PLAN` "Program 3, continued", `RESEED_PLAN` "EXECUTED by Program 9").
- 3 superseded prompt versions archived: `agent1_slot_b_reason_draft_v1/v2/v3`. Code loads only
  `reason_draft_v4` (`src/ultra_csm/agent1/slot_b.py:38`), so the older versions are history;
  the current version is the one canonical home. This alone cleared ~38 prompt-version near-dups.
- Provenance stripped from `SYNTHETIC_UNIVERSE_BIBLE.md` (reader-facing worldbuilding): four
  "(Program 19)" tags, one "(Program 8)", one "(Harvest 16)", and one "verified after
  authoring" receipt. Each passage is equally true with its authoring history deleted.

**False positives the triage exposed (fixed as linter defects in Phase 3, logged in DECISION_LOG):**

- `archive/` docs flagged as "on the reader-facing surface" (196 findings after the moves). An
  `archive/` segment is off-surface by construction. Fix: the directory scan skips it.
- Audience flags on `AGENT_PROFILE.md` and `TENANT_LOOPWAY_BIBLE.md`, driven entirely by the
  `IF/THEN` token. In this repo `IF/THEN` names a decision-record format and appears in
  citations and a metrics-table column, not in agent-address prose. Fix: dropped from HARNESS_RE.
- Provenance flags on `LIVE_INTEGRATION_FINDINGS.md:392` and `AGENT_PROFILE.md:17,93`, driven by
  `byte-identical`. It describes round-trip data fidelity and a `make`-target `PASS:` message
  there, not an authoring receipt. Fix: dropped from PROVENANCE_RE.

## Justification for the 73 findings the tuned linter still reports

The DoD permits a non-zero exit if every remaining finding is justified by file and line. Every
remaining finding falls in one of four justified classes.

**surface (10) -- deliberately curated evidence, not sequential process log.** `docs/README.md`
states the policy directly: "Program reports are receipts, not the reviewer path... remaining
root reports support specific claims linked from `LIMITS.md`." These 10 are exactly those cited
receipts and Core References, each doing reference work for a named claim:
`PROGRAM_REPORT_58/60/65/67/68/69/70` (each cited in `LIMITS.md`), `HANDOFF_SPIKE_SPEC.md`
(cited in `LIMITS.md`), `LIVE_INTEGRATION_FINDINGS.md` and `REPO_AUDIT.md` (Core References in
the index). Removing them would break the honest-limits evidence chain. The linter flags by
name and cannot read the index; a human keeps them on purpose.

**doc-length (21) and section-length (33) -- genuine long references that read as one unit.**
Each is a single-subject reference (`SYSTEM_ARCHITECTURE.md`, the three `TENANT_*_BIBLE.md`,
`SYNTHETIC_UNIVERSE_BIBLE.md`, the `QUALITY_*_SPEC.md` set, `ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md`,
`REAL_READY_ARCHITECTURE.md`, `OPERATOR_RUNBOOK.md`, `QUICKSTART.md`, `CAPABILITY_MAP.md`,
`CUSTOMER_VALUE_MODEL.md`, `OPERATING_PROOF.md`, `NONDETERMINISM_EVAL_HARDENING_SPEC.md`,
`UNIVERSE_V2_CONVENTIONS.md`, `SCREENCAST_SCRIPT.md`, `AGENT_PROFILE.md`). `DECISION_LOG.md`
(506 lines, 6 long sections) is the append-only changelog surface; length is inherent and
splitting it would fragment the one canonical home. Two are genuine split candidates flagged for
a later pass, not this one: `SYSTEM_ARCHITECTURE.md` (803 lines) and `SYNTHETIC_UNIVERSE_BIBLE.md`
(1082 lines). Splitting a 1000-line worldbuilding reference by hand is out of scope for a
docs-only hygiene pass and is recommended in `REPORT.md` instead.

**near-dup (7) and restatement (1) -- shared concepts across legitimately separate docs.**
`CUSTOMER_VALUE_MODEL.md:38` vs `SYSTEM_ARCHITECTURE.md:132` (62%): the value model and the
architecture each restate the same lifecycle premise from their own angle; collapsing to one
home would strip the reader who lands on either. `SYNTHETIC_UNIVERSE_BIBLE.md` vs
`UNIVERSE_V2_CONVENTIONS.md` (three pairs, 62-80%) and vs `TENANT_LOOPWAY_BIBLE.md:317` (61%):
the bible instantiates the conventions it shares, and cross-tenant boilerplate recurs by design.
`agent1_slot_b_expansion_v1.md` vs `agent1_slot_b_risk_v1.md` (73% and 100% at line 11): two
different active prompt slots that legitimately share one output-format instruction; both are
loaded by code. `LIVE_INTEGRATION_FINDINGS.md:23` vs `:159` (69%, within-doc): a findings
summary that restates a per-dataset result in its conclusion. Editing worldbuilding and active
prompt files by hand to chase a sub-80% overlap risks meaning for little reader gain.

**provenance (1) -- `AGENT_PROFILE.md:181`, a run-ledger table cell.** The "(Harvest 1)" mark
sits in a Quirks-ledger row (`| 2026-07-04 | Report 20, this retro (Harvest 1) | ... |`) whose
job is to track which run recorded each metric. That is changelog-style data, where run
provenance is the content, not stray history. Stripping it would delete a column value. Candidate
follow-up: add `AGENT_PROFILE` to the linter's `CHANGELOG_RE` allowlist (not done this pass; the
doc is only partly a ledger).
