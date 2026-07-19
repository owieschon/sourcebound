# Manifest reference

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
This reference defines the manifest fields and binding surfaces that sourcebound accepts. Use it when you need to protect a repository fact without guessing where that fact belongs.
<!-- sourcebound:end purpose -->

**[Create a binding from the runnable tutorial](learn/tutorial-catch-a-lying-doc.md)**.

Confirm the result with [`sourcebound check` and `sourcebound verify`](CLI.md).

## Binding types

The manifest accepts 3 binding types. This count is checked against the validator's canonical
registry; the generated table below owns their field-level contract.

This table comes from the manifest validator:

<!-- sourcebound:begin manifest-reference -->
| binding | required | verifies |
| --- | --- | --- |
| region | id, type, doc, region, extractor, source, renderer | Generated content matches source evidence |
| claim | id, type, doc, anchor, command, assertion | Command output; declared reader-facing prose when configured |
| symbol | id, type, doc, anchor, source | A source path or Python symbol still exists |
<!-- sourcebound:end manifest-reference -->

## Region example

Create `.sourcebound.yml` at the repository root:

```yaml
version: 1
bindings:
  - id: actions
    type: region
    doc: README.md
    region: actions
    extractor: python-literal
    source: {path: src/actions.py, symbol: ACTIONS}
    renderer: markdown-table
    columns: [name, tier]
```

Mark the generated destination:

```markdown
<!-- sourcebound:begin actions -->
<!-- sourcebound:end actions -->
```

Inside an `.mdx` document, use MDX comment expressions so the file remains valid MDX:

```mdx
{/* sourcebound:begin actions */}
{/* sourcebound:end actions */}
```

MDX policy, role, purpose, allowance, and region controls use the same
`{/* sourcebound:... */}` form. sourcebound normalizes those standalone controls for policy
evaluation; it does not evaluate any other expression.

The source assignment may be a list of dictionaries or a dictionary whose values are records. Constructor calls are read as keyword records. sourcebound reads the syntax tree; the [security model](SECURITY_MODEL.md) owns the execution boundary.

### Path glob bindings

The `path` extractor requires at least one matching file. A zero-match glob exits `3`, names the
binding and glob, and leaves the document unchanged. This prevents a removed directory from
rendering an empty list that looks current.

### Command pins

Manifest `type: claim` is the compatibility spelling for a command pin. It checks that an
allowlisted JSON command returns the configured expected value. Add `prose` to also verify that the
text appears under the document anchor. `prose` must include the JSON representation of `expected`,
so the value the reader sees is part of the same contract. A command pin without `prose` is a legacy
output-only contract; its receipt reports that the anchored prose was not checked. Use a generated
scalar region when sourcebound should own the bytes, or an accepted
[source claim check](#source-claim-checks) for bounded prose shapes that static extraction supports.

```yaml
assertion:
  json_path: $.collected
  operator: equals
  expected: 340
  prose: 340 records.
```

## Supported binding surface

This table comes from the public capability registry:

<!-- sourcebound:begin supported-bindings -->
| binding | source | output | check |
| --- | --- | --- | --- |
| command pin (`type: claim`) | Allowlisted JSON command | Configured assertion, with optional declared prose at a document anchor | Compare typed expected and observed values; verify declared anchored prose |
| region | Static Python, structured data, text, or paths | Table, list, scalar, or fenced text | Re-render and compare |
| symbol | Static path or Python symbol | Reference at a document anchor | Resolve the cited locator |
<!-- sourcebound:end supported-bindings -->

## Depth model

Keep the README focused on the point, first action, proof, and routing. Put procedures in guides and lookup material here. A binding keeps one canonical source for a fact; it does not require every fact to share one page.

Repositories do not configure a standard path. sourcebound bundles the policy pack compiled from [`STANDARD.md`](../STANDARD.md), and CI fails when the authored standard and compiled pack differ.

## Review contracts

`review_contracts` declare observe-only relationships between exact source and documentation
locators. They are not bindings and cannot create repair or gate authority:

```yaml
review_contracts:
  - id: delivery-limit-guidance
    mode: observe
    sources:
      - id: page-limit
        path: src/delivery.py
        extractor: python-symbol
        locator: Delivery.PAGE_LIMIT
    targets:
      - id: page-limit-guidance
        path: docs/delivery.md
        extractor: markdown-section
        locator: "#page-limits"
```

Every contract needs at least one source and one target. Locator IDs are unique within the
contract. A side cannot repeat the same path, extractor, and locator under another ID. A source
and target also cannot share that exact identity, because one locator change could otherwise satisfy
both sides. Point each target at the canonical, non-generated documentation input instead.
Configured projection outputs cannot be targets.

Each locator chooses one supported extractor and locator shape:

| extractor | locator | change evidence |
| --- | --- | --- |
| `python-symbol` | Dotted Python identifier | Normalized syntax. Comments, docstrings, formatting, and source positions do not count. |
| `markdown-section` | `#fragment-anchor` | Normalized visible text tokens under the selected rendered heading. |
| `structured-data` | JSON Pointer | Canonical JSON for the selected JSON, YAML, or TOML value. |

Markdown section boundaries come from parsed Markdown and MDX heading nodes. A section ends at the
next heading of the same or higher rank. Headings and text inside comments, fenced code,
frontmatter, ESM blocks, MDX expressions, or lowercase HTML flow blocks do not define or alter the
selected section. A parse failure, including a missing Node.js 20 runtime, leaves the locator
unresolved.

### Review work limits

The limits bound manifest size and evaluation work:

| input | maximum | enforcement |
| --- | ---: | --- |
| Contracts per manifest | 64 | Manifest validation |
| Locators per contract, sources and targets combined | 32 | Manifest validation |
| Locators across all contracts | 256 | Manifest validation |
| Unique paths across all contracts | 128 | Manifest validation |
| Bytes in one file at one ref | 1,000,000 | Locator resolution |
| Bytes read across base and head | 16,000,000 | Locator resolution |
| Nodes in one selected structured value | 50,000 | Locator resolution |

Base and head are separate inputs to the total byte budget. A manifest above a cardinality limit is
invalid. A file, aggregate-byte, parse, or structured-node overage makes the affected locator
unresolved and the contract `unknown`. Because the only supported mode is `observe`, that outcome
remains advisory.

Within one evaluation, sourcebound reads each unique path once per immutable ref. It reuses the
Python AST, structured-data parse, and batched Markdown or MDX parse for every locator on that
path. It also reuses the digest for an identical ref, path, extractor, and locator. These caches
bound repeated work; they do not persist across evaluations.

The comparison of two immutable refs produces one state:

| state | meaning |
| --- | --- |
| `unaffected` | No declared source locator changed. |
| `cochanged` | A source changed and every declared target changed. |
| `review-recommended` | A source changed and at least one declared target did not. |
| `unknown` | A locator is missing or cannot be resolved. |

Every state remains advisory in `mode: observe`. `cochanged` records two changes, not review
completion or semantic correctness. `unknown` exposes broken observation without changing the
gate. Source and target relationships are repository-declared; sourcebound does not infer them.
The impact graph preserves `affects` and `requests-review` edges for inspection, but those edges do
not add artifact roots, make an artifact covered, change `coverage_complete`, or authorize repair.
An unresolved or `review-recommended` contract can make the impact summary `recommended`; it
cannot make a gate fail.

## Source claim checks

The boundary is narrow. Two prose shapes are in scope: numeric collection counts and identifier
rows in a table under a `Columns` heading. `claims` ranks a static Python source when the subject,
locator name, and document ownership signals support the match. Counts require a shared file stem
or directory; identifier tables may also use an exact heading-to-locator match. A deep common path
is not ownership by itself. The detector proposes a relationship; it does not pretend to understand
arbitrary sentences or prove that both sides describe the same concept.

Accept a relationship once by recording its document anchor and static source locator:

```yaml
source_claim_checks:
  - id: fixture-count
    kind: count
    doc: docs/evaluation.md
    anchor: fixture-volume
    subject: fixtures
    source: src/evaluation_data.py
    locator: FIXTURES#count
```

The check stores no expected value. The number in the document and the statically extracted source
value remain the two values under comparison. `sourcebound claims` reports every accepted
relationship and bounded assessment candidates. Its JSON output distinguishes
`candidate_population`, `candidate_shown`, and `candidate_truncated`; a cap never looks like the
whole denominator. A missing accepted locator fails closed.

Use `identifier-set` for a reference section whose `Columns` block should match the public keys of
a static Python mapping. Its locator ends in `#keys`, such as `USERS.fields#keys`. Leading
underscore keys remain implementation details and do not enter that public set.

`check --changed` evaluates an accepted relationship only when its document, source, or manifest
changed. Updating unrelated code does not create documentation work. Discovery does not repair
prose; update the documented value or the accepted relationship, then run `claims` and `check`
again.

## Binding sensitivity inputs

Use this receipt when you need to know whether one proposed identifier-set check actually depends
on one independently selected source fact. It is a dependency test, not a semantic verdict.

The command keeps the provider proposal and the scorer-controlled fact in separate files:

```bash
FACT_SHA256="$(shasum -a 256 mutation-target.json | awk '{print $1}')"
sourcebound binding sensitivity \
  --proposal proposal.json \
  --fact mutation-target.json \
  --fact-sha256 "$FACT_SHA256" \
  --format json
```

`sourcebound.binding-proposal.v1` contains a full `repository_commit` and one `relationship` with
`id`, `kind`, `doc`, `anchor`, `subject`, `source`, and `locator`.
`sourcebound.mutation-target.v1` binds the same commit, source, locator, and kind to one `member`, the
baseline `value_sha256`, and either `configured-source-claim` or `frozen-evaluation-fact` as its
selection basis. The basis is provenance, not semantic authority. The `--fact-sha256` argument pins
the complete target file before execution.

The first release supports Python `identifier-set` facts backed by a direct static mapping or a
mapping-valued constructor keyword. It reads committed UTF-8 blobs with Git, parses syntax without
importing the module, and applies one deterministic key rename in a disposable directory. No target
code runs. Duplicate
keys, dynamic mappings, command pins, plugins, path globs, and any target that needs code execution
return `unsupported`.

`sourcebound.binding-sensitivity.v1` reports one state:

| state | meaning |
| --- | --- |
| `sensitive` | The relationship was current, then became stale after the frozen fact changed. |
| `insensitive` | The relationship stayed current after a supported fact change. |
| `invalid` | The baseline, commit, frozen fact, or caller state did not satisfy the preconditions. |
| `unsupported` | No safe first-party mutation exists for the selected static shape. |

Sensitive exits `0`, insensitive exits `1`, invalid exits `2`, and unsupported exits `3`. Every
receipt sets `semantic_relationship_authorized` to false. Even a semantically wrong table can go
red when its identifier shape matches the selected source; only an independent semantic scorer can
authorize that relationship.

## Manifest versions

Version 2 removes the `network` key from allowed commands because sourcebound does not provide an
operating-system network sandbox. Version 1 remains readable. If it contains `network: false`,
sourcebound marks that field as deprecated; it neither blocks nor counts network traffic. Run
`sourcebound migrate --write` to remove the field with a rollback backup.

## Structured visual projections

A visual record owns the meaning shared by an annotated human image and its agent-readable text
equivalent. Use one when a screenshot or diagram needs numbered callouts, a dark variant, or a
complete nonvisual explanation. The record is data; generated outputs are projections and must not
be edited independently.

The `sourcebound.visual.v1` record requires intrinsic dimensions so percentage coordinates remain
stable as the image scales. `src` and `src_dark` are HTTPS URLs or repository-relative paths.
Alternative text and captions are single lines. The agent output keeps the full explanation and
every numbered callout:

```yaml
schema: sourcebound.visual.v1
id: queue-flow
kind: screenshot
src: docs/assets/queue-light.png
src_dark: docs/assets/queue-dark.png
width: 1200
height: 800
alt: Queue dashboard with the worker status panel open
caption: The worker panel shows which queue owns the stalled job.
description: |
  The dashboard lists three queues. The selected queue opens a worker panel
  whose status and retry action apply only to that queue.
annotations:
  - id: retry-action
    x: 81
    y: 74.25
    title: Retry action
    description: Retries the selected failed job after confirmation.
```

Declare both destinations under `projections.visuals`. The human output is portable Markdown or
MDX built from native elements, with numbered overlay links and an adjacent annotation key. The
agent output is Markdown containing the record identity, source digest, complete text equivalent,
and labeled coordinates:

```yaml
projections:
  visuals:
    - id: queue-flow
      source: docs/visuals/queue-flow.yml
      human_output: docs/generated/queue-flow.mdx
      agent_output: .sourcebound/visuals/queue-flow.md
```

Run `sourcebound project` to write both outputs. Run `sourcebound project --check` in CI so a changed
asset record cannot leave either audience on an older projection. Local image paths must exist;
record IDs, annotation IDs, output paths, coordinates, dimensions, and unknown fields fail closed.
The [source-bound flow projection](generated/source-bound-flow.md) dogfoods this contract against
the diagram that introduces Sourcebound.

## Context request

`sourcebound.context-request.v1` compiles a provider-neutral evidence packet from the current commit.
The byte budget is mandatory. The request contains a full `repository_commit`, positive
`budget_bytes`, and one or more items.
Each item names an `id`, `kind`, repository-relative `path`, `start_line`, `end_line`, `authority`,
`relationship`, `reason`, numeric `rank`, and boolean `required` and `instruction` flags.

Supported authorities, strongest first, are `accepted-policy`, `direct-evidence`, `generated`,
`repository-doc`, and `hypothesis`. Instruction authority requires both `accepted-policy` and a
`policy` or `instruction` kind. Other prose stays data.

Required evidence is selected before optional context. Within each group, authority, rank, and item
ID produce a stable order. An optional item that exceeds the byte budget is excluded with
`budget-exhausted`. A required item that does not fit produces `required-over-budget` and makes the
bundle `unknown`.
