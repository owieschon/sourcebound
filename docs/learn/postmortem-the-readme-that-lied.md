# Postmortem: the README that lied

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
This case study is for maintainers whose documentation corpus feels polished but has lost a trustworthy reader path. It shows how one real repository separated current guidance from process exhaust, measured the result, and exposed which improvements still required human judgment.
<!-- sourcebound:end purpose -->

**[Inspect the archived before-and-after record](../archive/v0/ultra-csm-before-after.md)**.

The [recorded result](../archive/v0/ultra-csm-before-after.md) supplies the measurements and
examples rendered below.

The repository did not have one spectacularly false page. It had a quieter failure: current
guidance, superseded prompts, handoff notes, and authoring history all looked equally official.
Nothing in the prose announced which layer a reader had entered.

This is a historical cleanup of `ultra-csm`, not a claim about that repository's current state.

## What the scan found

The first pass reported 280 findings. It grouped them by structure, repeated text, length, source
history, and intended reader:

<!-- sourcebound:begin postmortem-measurements -->
| measure | before | after |
| --- | --- | --- |
| Total findings | 280 | 73 (all justified in `NOTES.md`) |
| surface (process artifact on reader surface) | 91 | 10 (cited evidence, per `docs/README.md`) |
| section-length | 93 | 33 (genuine long references) |
| near-dup | 54 | 7 (shared concepts across separate docs) |
| doc-length | 22 | 21 (genuine long references) |
| provenance | 11 | 1 (a run-ledger table cell) |
| audience | 7 | 0 |
| restatement | 2 | 1 |
<!-- sourcebound:end postmortem-measurements -->

The count fell because the reader surface got smaller and the checker lost false positives. It did
not fall because thresholds were loosened. The remaining findings were reviewed and justified in
the source repository. The [archived case](../archive/v0/ultra-csm-before-after.md) owns the
complete record.

## Three changes did most of the work

The cleanup made each document answer a harder question than "is this Markdown useful somewhere?"
It asked whether the page belonged on the current reader surface:

<!-- sourcebound:begin postmortem-examples -->
| case | before | after |
| --- | --- | --- |
| process exhaust off the reader surface | an agent-to-agent handoff sat in the tracked doc tree a reader browses | relocated into the archive convention the repo already used, history intact |
| one canonical home for a versioned prompt | four versions of one prompt tracked side by side, each a near-duplicate of the last | only the version `src/ultra_csm/agent1/slot_b.py:38` loads remains on the surface |
| provenance stripped from a reader-facing reference | a worldbuilding reference tagged its content with the program that authored it | each passage is equally true, with the authoring history removed |
<!-- sourcebound:end postmortem-examples -->

The first change moved handoffs and status notes into the repository's archive convention. The
second left one loaded prompt version on the current surface and preserved older versions as
history. The third removed authoring-program labels from reference prose that stayed true without
them.

The result was not tidier wording. It was a corpus whose paths had different meanings.

The [archived case](../archive/v0/ultra-csm-before-after.md) preserves the full before-and-after
page inventory behind these three changes.

## What the numbers do not prove

A lower hygiene count does not prove that every sentence is accurate, helpful, or well taught.
Several remaining findings were legitimate long references or shared concepts. Three reductions
came from correcting the linter itself. The evidence supports a narrower claim: structural noise
became measurable, most of it left the current reader path, and the exceptions became explicit.

That boundary matters. Corpus checks can find likely process exhaust, duplicate language, and
misplaced provenance. A source binding is still required when a specific product claim must fail
after its defining code changes. [Catch a lying doc](tutorial-catch-a-lying-doc.md) demonstrates that
second mechanism on one fact.

## The reusable decision

For every page, ask: if this vanished from the current documentation surface, would a reader lose
current product truth or only authoring history? Keep the first in the reader path. Preserve the
second in version history or an archive whose name makes its status clear.

Then bind the factual spine that remains. Structure makes the right page findable; source evidence
makes its checkable claims answerable.
