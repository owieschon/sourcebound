# ultra-csm before and after: the hygiene pass in numbers and examples

This records what the doc-standard system caught on one real repo and what the by-hand cleanup
changed. It is the seed of the eventual public artifact's worked example.

## The numbers

| Measure | Before | After |
| --- | --- | --- |
| Total findings | 280 | 73 (all justified in `NOTES.md`) |
| surface (process artifact on reader surface) | 91 | 10 (cited evidence, per `docs/README.md`) |
| section-length | 93 | 33 (genuine long references) |
| near-dup | 54 | 7 (shared concepts across separate docs) |
| doc-length | 22 | 21 (genuine long references) |
| provenance | 11 | 1 (a run-ledger table cell) |
| audience | 7 | 0 |
| restatement | 2 | 1 |

The drop came from three by-hand moves and three linter-defect fixes, not from loosening the
rules. 33 orphaned process docs and 3 superseded prompt versions moved into `docs/archive/`;
seven provenance marks were stripped from one reader-facing reference; the linter stopped
flagging archived history, a decision-record token, and a data-fidelity phrase.

## Example 1: process exhaust off the reader surface

Before -- an agent-to-agent handoff sat in the tracked doc tree a reader browses:

```text
docs/EXECUTOR_HANDOFF.md
docs/EXECUTOR_HANDOFF_LANE_E.md ... _J.md
docs/NEXT_DISPATCH.md
BLOCKED.md   STATUS.md
```

After -- relocated into the archive convention the repo already used, history intact:

```text
docs/archive/EXECUTOR_HANDOFF.md
docs/archive/NEXT_DISPATCH.md
docs/archive/BLOCKED.md   docs/archive/STATUS.md
```

The reader path is now what `docs/README.md` curates; the pickup notes stay reachable in git.

## Example 2: one canonical home for a versioned prompt

Before -- four versions of one prompt tracked side by side, each a near-duplicate of the last:

```text
docs/prompts/agent1_slot_b_reason_draft_v1.md   # ~38 near-dup findings across v1-v4
docs/prompts/agent1_slot_b_reason_draft_v2.md
docs/prompts/agent1_slot_b_reason_draft_v3.md
docs/prompts/agent1_slot_b_reason_draft_v4.md   # the version code actually loads
```

After -- only the version `src/ultra_csm/agent1/slot_b.py:38` loads remains on the surface:

```text
docs/prompts/agent1_slot_b_reason_draft_v4.md
docs/archive/agent1_slot_b_reason_draft_v1.md   # superseded, held in archive
```

## Example 3: provenance stripped from a reader-facing reference

Before -- a worldbuilding reference tagged its content with the program that authored it:

```text
**Density subsection (Program 19).** Five new email pairs (day 100, 130, ...
**Phase U5.F density extension (Program 8).** Three new email exchanges, ...
### New-stakeholder-unengaged -- `oakmont-logistics` (Harvest 16)
... unchanged by construction -- verified after authoring. One legitimate, ...
```

After -- each passage is equally true, with the authoring history removed:

```text
**Density subsection.** Five new email pairs (day 100, 130, ...
**Phase U5.F density extension.** Three new email exchanges, ...
### New-stakeholder-unengaged -- `oakmont-logistics`
... unchanged by construction. One legitimate, ...
```
