# Work order: consolidate, tune, and prove the documentation-standard system

**Your one job:** package Owen's scattered documentation-standard system into a coherent
unit in this workspace, tune it, run it on a real repo (ultra-csm first) to clean up that
repo's documentation, then re-tune based on what real docs expose. Do not publish anything.
Do not extract a public repo yet. This is the harden-and-prove phase that must pass before
any public version is built.

Write everything you produce to the standard you are consolidating. An agent working on a
doc-quality system that writes sloppy docs has failed the assignment. No em dashes. Never use
the phrase "load-bearing" (Owen's rule; the standard itself currently breaks it, which is one
of the fixes below).

## What exists and where (survey these before touching anything)

The system is nine files across two homes. The four that carry real, shareable value:

| File | Role |
| --- | --- |
| Global writing-standard file (~223 lines) | The standard. Three tiers: sentence voice, single-doc medium boundary, corpus. Single source of truth. |
| `~/scripts/doc-hygiene.py` (~253 lines) | The corpus linter (tier 3). Seven deterministic checks, stdlib only, exit 1 on findings, `--json`. |
| `~/scripts/quality-gate.py` (~153 lines) | The write gate (tier 1). Blocks sentence-level tells on every agent write. |
| Global scrub adapter | Runs doc-hygiene as a companion in the pre-publish sweep. |

The other five are personal wiring you should read for context but not repackage: the
the global documentation-register clause and `~/AGENTS.md` "Writing register"
clause (load the standard into agent runtimes), the `reference_writing_style_standard`
memory, the `~/second-brain/agentic-eng/wiki/owen-documentation-precision.md` brain pointer,
and the hook registration in the global agent settings (quality-gate on PreToolUse, dod-gate
on Stop).

Prior grounding you can rely on: a full audit of ultra-csm ran this session and reported a
280-finding doc-hygiene scan (roughly 91 process-artifact hits, plus near-dups and
over-length), and confirmed `docs/READING_PATH.md` already curates the intended reader-facing
slice. ultra-csm's working tree has uncommitted UI edits and 175 branches; treat it carefully.

## Boundaries (do not cross)

- **The live global config keeps running.** Do not edit the global writing standard,
  `~/scripts/*.py`, or global agent settings in place during tuning. Consolidate and tune
  COPIES in this workspace. Propagating tuned versions back to the live config is a separate,
  Owen-approved step you only recommend, never perform (it changes every future session).
- **ultra-csm: documentation only, on a branch.** Never modify `src/`, `tests/`, or any
  `.py`/`.ts` file in ultra-csm. Create a fresh branch off the current checkout; do not disturb
  the uncommitted UI edits (check `git -C ~/dev/ultra-csm status` first and leave those files
  alone). Do not merge to main, do not push, do not touch other branches.
- **Publish nothing.** No new public repos, no remotes, no GitHub. This phase ends at a local
  report.
- **The linters are detect-only.** They never rewrite. You do the doc fixes by hand, guided by
  the linter output and the standard. Judgment does the fixing; the tools only find.

## Phase 0: Ground

1. Read the four core files and the five wiring files listed above. Read `~/dev/ultra-csm/docs/READING_PATH.md`.
2. Run the linters as-is to see current behavior before changing them:
   ```bash
   python3 ~/scripts/doc-hygiene.py ~/dev/ultra-csm            # baseline finding count
   python3 ~/scripts/doc-hygiene.py "$CLEAN_DOCS_STANDARD" # does the standard pass itself?
   ```
3. Write a two-paragraph "current state" note in `~/dev/doc-standard/NOTES.md`: what the system
   is, and the baseline ultra-csm finding count. Do not change anything yet.

## Phase 1: Package and tune (in this workspace only)

1. Copy the four core files into `~/dev/doc-standard/`: `STANDARD.md` (from writing-style.md),
   `doc-hygiene.py`, `quality-gate.py`, and `skill/SKILL.md`. Keep a verbatim backup of each
   original alongside (`*.orig`) so every change is diffable.
2. **Dogfood the standard against itself.** Run `doc-hygiene.py` on `STANDARD.md` and walk
   `STANDARD.md` through its own section 7 pre-publish checklist by hand. Fix what it flags.
   Specifically: remove both "load-bearing" uses (name what actually does the work instead),
   and confirm the standard obeys its own corpus and medium rules.
3. **Tune the linter's opinions where the code, not the doc, is the problem.** Review
   `doc-hygiene.py`'s `PROCESS_RE`, `HARNESS_RE`, `PROVENANCE_RE`, and the length/Jaccard
   thresholds. Do not tune blind; tune against evidence from Phase 2. For now only fix outright
   bugs and note candidate adjustments in `NOTES.md`.
4. Confirm the packaged linter still runs and its behavior matches the live one on a sample
   (byte-identical output on the same input, minus your intended fixes).
5. Record every consequential choice in `~/dev/doc-standard/DECISION_LOG.md`: context, the
   options, the choice and why, reversibility. One honest paragraph each.

## Phase 2: Run on ultra-csm and clean up its documentation

1. `git -C ~/dev/ultra-csm status`: note the uncommitted files; you will not touch them. Create
   a branch: `git -C ~/dev/ultra-csm switch -c docs/hygiene-pass-1`.
2. Run the tuned linter: `python3 ~/dev/doc-standard/doc-hygiene.py ~/dev/ultra-csm --json > ~/dev/doc-standard/ultra-csm-findings.json`.
3. **Triage every finding into real vs false positive.** For each: is this doc genuinely
   process-exhaust that belongs in git history or an `archive/`? A genuine near-duplicate where
   one canonical home should win? Genuinely over-length without justification? Or is the linter
   wrong (a reader-facing doc that legitimately uses harness vocabulary, a doc that earns its
   length)? Write the triage in `NOTES.md`.
4. **Fix the real findings by hand, docs only.** Move process artifacts off the reader-facing
   surface (into `archive/` outside the doc tree, or delete if git already holds them); collapse
   duplicates to one canonical home with siblings citing it; split or justify over-length docs;
   strip provenance and receipts from reference docs. Use `READING_PATH.md` as the definition of
   the reader-facing surface. Every "don't" you remove keeps its "instead" if the content still
   matters.
5. Re-run the linter until it exits 0, or until every remaining finding has a one-line written
   justification for why it stays.
6. Keep a `~/dev/doc-standard/ultra-csm-before-after.md`: the baseline count, the final count,
   and two or three representative before/after snippets. This is also the seed of the eventual
   public artifact's example.

## Phase 3: Re-tune from what ultra-csm exposed

1. Every false positive from Phase 2 triage is a linter defect. Adjust the patterns or
   thresholds in the workspace `doc-hygiene.py` to remove it without hiding real findings, and
   log the change in `DECISION_LOG.md`.
2. Every real problem the linter missed is a coverage gap. If it is mechanically detectable, add
   the check; if it needs judgment (for example "does each section lead with its takeaway"),
   record it in the standard's honest-seam section as instruction-only, and note where an
   LLM-judge pass would slot in. Do not fake a mechanical check for a judgment call.
3. If the real-repo experience revealed a genuine gap in the standard itself (as ultra-csm
   originally exposed the corpus tier), update `STANDARD.md` and dogfood it again.
4. Re-run the tuned linter on ultra-csm to confirm the system is now clean-or-justified and
   false-positive-free.

## Phase 4: Report and stage, do not proceed

1. Write `~/dev/doc-standard/REPORT.md` (to the standard): what the system caught on ultra-csm,
   what you tuned and why, the before/after numbers, and the honest seam that remains.
2. Recommend, do not perform, the propagation back to live config: which tuned files should
   replace the global writing standard and `~/scripts/*.py`, and the exact commands, for Owen
   to run. Flag the global blast radius.
3. List the next repos to run on in priority order (Alice/job-search has PII, so note it needs a
   scrub-and-slice first; bank-mcp and reter-public are clean). Do not run them; ultra-csm is the
   only repo this order authorizes touching.
4. Stop. Surface the report to Owen. The public-repo extraction is the next phase and is not in
   scope here.

## Next layers (direction only; do NOT build any of these in this pass)

These come after the deterministic core is proven on ultra-csm. Record them in REPORT.md as
recommendations; build none of them here. The discipline this system teaches applies to the
system itself: prove one layer before adding the next. Building these before the core is
validated on one real repo is the exact scope-creep that left the standard half-finished across
five repos. The sequence, in order:

1. **llms.txt generator (next; small and real).** One command over the cleaned doc tree emits an
   agent-addressable index of the same docs a human reads. It is the concrete proof that the human
   surface and the agent surface are one source with two projections, not two hand-written copies.
   The source documentation corpus ships exactly this (`llms.txt`); it is a small tool, not an engine.
2. **Round-trip eval (the differentiator; treat as the headline).** Give an agent only a doc and
   have it answer questions or reconstruct the interface the doc describes, then score whether it
   could. This measures the real goal directly: is the doc usable context for an agent. It is a
   positive test (can this be used) rather than a negative one (does this contain tells), and it is
   the sharpest available measure of the unified human-and-agent objective.
3. **Content-grounding as claim-against-source verification (only when it can be verification-shaped).**
   The dangerous residue class is a factual claim with no support: "24/24 tests pass" when they do
   not. The correct check runs the claim against its source: run the tests, read the cited file,
   compare the number. It is NOT an LLM judge asked "does this seem unsupported"; a judge-by-vibes
   check confidently false-flags and confidently misses, the failure mode already paid for once.
   Build it only for claims that carry a runnable or readable source; leave the rest honestly
   unchecked.
4. **Derive-from-source (a scoped demo, not a build).** Show one existing doc rendered from ground
   truth (ultra-csm's `DEPLOYMENT_READINESS.md`, already praised by reviewers) and explain why a doc
   bound to source cannot fabricate. Demonstrate the principle with the one real example. Do not
   build a general doc generator; that is an engine that sprawls, and the value is the principle,
   not the machine.

The payoff of holding this line: llms.txt and the round-trip eval, added on top of a proven
deterministic core, make this the system that generates good documentation from ground truth and
proves it usable by both a human and an agent, with an honest account of what it can and cannot
guarantee.

## Definition of done (each line is a check that must pass)

- `python3 ~/dev/doc-standard/doc-hygiene.py ~/dev/ultra-csm` exits 0, or `NOTES.md` justifies
  every remaining finding by file and line.
- `grep -ri "load.bearing" ~/dev/doc-standard/STANDARD.md` returns nothing.
- `STANDARD.md` passes its own section 7 pre-publish checklist (walked by hand, recorded).
- ultra-csm changes are documentation only: `git -C ~/dev/ultra-csm diff --name-only main...docs/hygiene-pass-1 | grep -vE '\.(md|txt|rst)$'` returns nothing.
- The ultra-csm uncommitted UI files from Phase 2 step 1 are unchanged by you.
- Nothing was pushed; no public repo exists; the live agent configuration and `~/scripts` files are
  unmodified (only workspace copies changed).
- `REPORT.md`, `DECISION_LOG.md`, and `ultra-csm-before-after.md` exist and are written to the
  standard.
- The next-layers direction is recorded as recommendations only, not built: `grep -qiE "round-trip|llms\.txt" ~/dev/doc-standard/REPORT.md` exits 0, and no generator, eval, or judge tool was added to the workspace this pass.

## Voice rules (you are graded on these too)

No em dashes. No "load-bearing." Ban the booster words the gate blocks: seamless, powerful, simply, comprehensive, leverage, utilize. <!-- slop-ok: banned-word registry named as negative examples -->
One claim per sentence. Prose for why, code for do-this, tables for lookup, numbered steps for
sequence. Name each doc's one job in its first line. Every "don't" ships with its "instead."
Exemplify the standard you are hardening.
