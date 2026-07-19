# Deep dive: the deterministic seam

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
This explanation is for maintainers deciding where a model may enter a documentation pipeline without weakening its gate. It shows who selects facts, phrases prose, writes files, and decides pass or fail, so you can inspect each boundary in the architecture and code.
<!-- clean-docs:end purpose -->

**[Run the drift tutorial](tutorial-catch-a-lying-doc.md)** to see the boundary fail and recover.

The final check produces a [verification result](../SUPPORT.md#record-local-outcomes) whose
`"ok"` field is `true`.

The short version is mechanical: a model may choose a fact identifier and an allowlisted template,
but deterministic code renders the sentence and keeps the keys. Facts enter from declared evidence,
writes stay bounded to planned documents, and a deterministic result decides whether the repository
is current.

The [README architecture contract](../../README.md#how-the-pieces-fit) names the inputs and
job-specific exits. This page follows the three authority handoffs inside that path: evidence enters,
a provider may select an allowed presentation, and deterministic checks retain rendering and verdict
authority.

## Evidence authority

[`evaluate`](../../src/clean_docs/engine.py) owns the source-to-binding comparison. It loads the
manifest, creates a repository snapshot, dispatches only the declared extractor, renders the typed
value, and compares the result with the marked document region. Claim and symbol bindings take the
same route through typed results.

This is the first side of the seam: source configuration selects which facts exist. A model does not
discover an extra capability, widen the selected repository scope, or turn an unsupported surface
into an accepted claim. The [manifest page](../REFERENCE.md) owns the supported binding surface.

## Phrasing boundary

[`build_model_record`](../../src/clean_docs/phrasing.py) receives inventory facts that already
exist. Its prompt exposes an allowlist of prose templates and asks for fact identifiers plus template
names, not open-ended product copy. The parser rejects unknown facts, duplicate facts, unsupported
templates, malformed responses, and more than five drafts.

The deterministic renderer turns the selected fact and template into prose. That prose is not a
source. If the provider fails, the operation stops before a repository write. The
[security model](../SECURITY_MODEL.md) defines the surrounding process and host boundaries without
duplicating them here.

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
| Select a supplied fact/template pair | Bounded model path | Selection may vary without changing factual authority |
| Render final text | Deterministic renderer | The provider cannot add prose or facts |
| Write documentation | Explicit derive or drive path | Unrelated prose must remain untouched |
| Decide pass or fail | Deterministic checks | CI needs the same answer without credentials or judgment drift |

Use a human or model to judge motivation, pedagogy, and whether the chosen facts are enough. Use the
gate to prove that declared facts, locators, and projections still match. The seam is not a claim
that all prose is true forever. It is the line that prevents the checkable spine from drifting
silently.

Run [the tutorial](tutorial-catch-a-lying-doc.md) to exercise that boundary, or use the
[extension guide](../EXTENSIONS.md) when a source needs a new deterministic adapter.
