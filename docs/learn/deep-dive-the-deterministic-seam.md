# Deep dive: the deterministic seam

<!-- clean-docs:purpose -->
This explanation is for maintainers deciding where model judgment may enter a documentation pipeline without weakening its gate. It separates evidence selection, prose phrasing, repository writes, and pass or fail authority so you can inspect the boundary in both the architecture and the implementation.
<!-- clean-docs:end purpose -->

The short version is memorable because it is mechanical: a model may hold the pen, but it never
gets the keys. Facts enter from declared evidence, writes stay bounded to planned documents, and a
deterministic result decides whether the repository is current.

The [product system map](../../README.md#how-the-pieces-fit) shows the complete path and its text
equivalent. This page follows the three authority handoffs inside it: evidence enters, phrasing may
change its form, and deterministic checks retain the verdict.

## Evidence authority

[`evaluate`](../../src/clean_docs/engine.py) owns the source-to-binding comparison. It loads the
manifest, creates a repository snapshot, dispatches only the declared extractor, renders the typed
value, and compares the result with the marked document region. Claim and symbol bindings take the
same route through typed results.

This is the first side of the seam: source configuration selects which facts exist. A model does not
discover an extra capability, widen the selected repository scope, or turn an unsupported surface
into an accepted claim.

## Phrasing boundary

[`build_model_record`](../../src/clean_docs/phrasing.py) receives inventory facts that already
exist. Its prompt exposes an allowlist of prose templates and asks for fact identifiers plus template
names, not open-ended product copy. The parser rejects unknown facts, duplicate facts, unsupported
templates, malformed responses, and more than five drafts.

The returned sentence is therefore a presentation of supplied evidence. It is not evidence. If the
provider fails, the operation stops before a repository write. The [security model](../SECURITY_MODEL.md)
defines the surrounding process and host boundaries without duplicating them here.

## Gate authority

[`build_outcome_receipt`](../../src/clean_docs/outcomes.py) combines deterministic audit, inventory,
binding, projection, and changed-file results. Its `ok` value follows those counts. It does not ask a
provider whether the prose sounds supported.

That distinction keeps failure actionable. A stale region names its binding and source. A missing
symbol names its locator. A model score could express judgment about clarity, but it cannot replace
the repeatable evidence that made the check fail.

## Why the seam is useful

Pure generation can produce fluent documentation whose factual scope is impossible to audit. Pure
templates can keep facts current while flattening every explanation into reference prose. The seam
keeps both tools in their honest roles:

| Responsibility | Owner | Why |
| --- | --- | --- |
| Select facts and scope | Manifest plus extractor | The input must be reproducible at a repository ref |
| Phrase supplied facts | Deterministic renderer or bounded model path | Presentation may vary without changing authority |
| Write documentation | Explicit derive or drive path | Unrelated prose must remain untouched |
| Decide pass or fail | Deterministic checks | CI needs the same answer without credentials or judgment drift |

Use a human or model to judge motivation, pedagogy, and whether the chosen facts are enough. Use the
gate to prove that declared facts, locators, and projections still match. The seam is not a claim
that all prose is true forever. It is the line that prevents the checkable spine from drifting
silently.

Run [the tutorial](tutorial-catch-a-lying-doc.md) to exercise that boundary, or use the
[extension guide](../EXTENSIONS.md) when a source needs a new deterministic adapter.
