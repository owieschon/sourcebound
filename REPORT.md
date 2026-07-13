# REPORT: the documentation-standard system, hardened and proven on ultra-csm

This report states what the system caught on one real repo, what was tuned and why, and what
remains honest but unmechanized. It ends with a propagation recommendation for Owen to run, and
the next repos in priority order. Nothing here was published; the live config was not modified.

## What the system caught

Run against ultra-csm, the corpus linter reported 280 findings. The by-hand cleanup and three
linter-defect fixes brought that to 73, every one of which is justified by file and line in
`NOTES.md`. The reductions came from moving process exhaust off the reader surface, not from
relaxing the rules.

| Measure | Before | After |
| --- | --- | --- |
| Total | 280 | 73 (all justified) |
| surface | 91 | 10 |
| section-length | 93 | 33 |
| near-dup | 54 | 7 |
| doc-length | 22 | 21 |
| provenance | 11 | 1 |
| audience | 7 | 0 |
| restatement | 2 | 1 |

The real catches were genuine: 33 orphaned handoffs, dispatches, receipts, blocked/status notes,
executed plans, and superseded prompt versions were sitting on the tracked doc surface a reader
browses, and one reader-facing worldbuilding reference carried seven authoring-provenance marks.
The repo's own index (`docs/README.md`, `LIMITS.md`) defined which docs were reader-facing, so
the cleanup honored the curation the repo had already started rather than sweeping by filename.
Full before/after examples are in `ultra-csm-before-after.md`.

## What was tuned, and the evidence that drove each change

Three of the four core files carry shareable value; only the linter's opinions needed tuning,
and only where a real doc, not the code, was the false positive. Each change is logged with its
alternative in `DECISION_LOG.md`.

- **Skip `archive/` in the directory scan.** Evidence: 51 already-archived program reports were
  flagged "on the reader-facing surface" before any move, and 196 findings sat inside
  `docs/archive/` after the moves. An archive is off-surface by construction. A single explicit
  file target still lints, so an archived doc can be inspected on demand.
- **Drop `IF/THEN` from the harness vocabulary.** Evidence: the only audience findings on genuine
  docs (`AGENT_PROFILE.md`, `TENANT_LOOPWAY_BIBLE.md`) were driven entirely by this token, which
  here names a decision-record format and appears in citations and a metrics-table column, not in
  agent-address prose. The strong signals ("next executor", "pick up this branch", "worktree")
  remain.
- **Drop `byte-identical` from the provenance pattern.** Evidence: it flagged a round-trip
  data-fidelity claim (`LIVE_INTEGRATION_FINDINGS.md:392`) and a `make`-target `PASS:` message
  (`AGENT_PROFILE.md`), both technical claims about data rather than authoring receipts. The
  `(Program|Wave|Harvest N)` tags carry the provenance-as-canon signal.

The standard was dogfooded against itself: three uses of the prohibited "does-the-essential-work"
compound were replaced with the actor that does the work, 24 em dashes were normalized to the
ASCII double-hyphen the scripts already use, and a first-line justification for staying one file
was added. The write gate (`quality-gate.py`) and the scrub skill needed no change.

## The honest seam that remains

Three corpus rules resist mechanization, so the tuned `STANDARD.md` now records them as
judgment-only in its section 6 honest seam, with no faked regex behind them:

- An executed or superseded plan is process exhaust; a live plan is a reference. The status line
  separates them, not the filename (`RESEED_PLAN` "EXECUTED" vs `EVAL_PLAN` "active").
- A doc about agent operation is not a doc written for a future agent. The second person
  separates them, not the vocabulary (an agent profile legitimately says "worktree").
- Each section should lead with its takeaway. No token pattern detects a missing lead.

Each names where an LLM-judge pass would slot in. Until then a human owns them, because a
judge-by-pattern check for a judgment call misfires in both directions.

## Propagation recommendation (for Owen to run; do not treat as done)

The tuned files live only in `~/dev/doc-standard/`. Propagating them edits the global config that
every future session reads, so it is Owen's call, not this pass's. Blast radius: `writing-style.md`
is loaded into agent sessions through global instruction registers, so its register governs
future writing; `doc-hygiene.py` runs inside the scrub
skill and the pre-publish sweep, so its opinions govern what every future scan flags. Diff before
copying.

```bash
# review first
diff "$CLEAN_DOCS_STANDARD" ~/dev/doc-standard/STANDARD.md
diff ~/scripts/doc-hygiene.py   ~/dev/doc-standard/doc-hygiene.py

# then, if the diffs read right, replace the live copies
cp ~/dev/doc-standard/STANDARD.md    "$CLEAN_DOCS_STANDARD"
cp ~/dev/doc-standard/doc-hygiene.py ~/scripts/doc-hygiene.py
```

`quality-gate.py` and the scrub `SKILL.md` are byte-identical to their originals; do not copy
them, there is nothing to propagate. The linter changes are low-risk because all three only
remove false positives; the standard changes are the em-dash normalization, the prohibited-phrase
removal, and the honest-seam addition.

## Next repos, in priority order (do not run yet; this pass authorized only ultra-csm)

1. `bank-mcp` -- clean, no PII, small doc surface; the fastest second proof.
2. `reter-public` -- clean, already portfolio-shaped; good for the one-canonical-home checks.
3. `Alice / job-search` -- **needs a scrub-and-slice first.** It carries PII, so run the scrub
   skill and reduce to the reader-facing slice before the doc-hygiene pass, not after.

## Next layers (recommendations only; none was built this pass)

The discipline this system teaches applies to itself: prove one layer before adding the next.
The deterministic core is now proven on one real repo, which is the gate these must clear before
they are built. Recorded here so they are not lost, and deliberately not started:

1. **llms.txt generator (next; small and real).** One command over the cleaned doc tree emits an
   agent-addressable index of the same docs a human reads, proving the human surface and the agent
   surface are one source with two projections.
2. **Round-trip eval (the differentiator).** Give an agent only a doc, have it reconstruct the
   interface the doc describes, and score whether it could. This is a positive test (can this be
   used as context) rather than a negative one (does this contain tells), and it measures the real
   goal directly.
3. **Content-grounding as claim-against-source verification.** Run a factual claim against its
   source (run the tests, read the cited file, compare the number). Build it only for claims that
   carry a runnable or readable source; it is not an LLM judge asked "does this seem unsupported."
4. **Derive-from-source (a scoped demo, not an engine).** Show one existing doc rendered from
   ground truth (`ultra-csm/docs/DEPLOYMENT_READINESS.md`) and explain why a doc bound to source
   cannot fabricate. Demonstrate the principle with the one example; do not build a general
   generator.

## Status

Phase 0 through Phase 4 complete. The ultra-csm cleanup is committed on `docs/hygiene-pass-1`
(documentation only, based on `main`), not pushed and not merged. The public-repo extraction is
the next phase and is out of scope here.
