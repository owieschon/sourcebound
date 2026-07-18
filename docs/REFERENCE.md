# Manifest reference

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
This reference defines the manifest fields and binding surfaces that clean-docs accepts. Use it when you need to protect a repository fact without guessing where that fact belongs.
<!-- clean-docs:end purpose -->

**[Create a binding from the runnable tutorial](learn/tutorial-catch-a-lying-doc.md)**.

Confirm the result with [`clean-docs check` and `clean-docs verify`](CLI.md).

## Binding types

The manifest accepts 3 binding types. This count is checked against the validator's canonical
registry; the generated table below owns their field-level contract.

This table comes from the manifest validator:

<!-- clean-docs:begin manifest-reference -->
| binding | required | verifies |
| --- | --- | --- |
| region | id, type, doc, region, extractor, source, renderer | Generated content matches source evidence |
| claim | id, type, doc, anchor, command, assertion | Command output matches the assertion; anchored prose is not inspected |
| symbol | id, type, doc, anchor, source | A source path or Python symbol still exists |
<!-- clean-docs:end manifest-reference -->

## Region example

Create `.clean-docs.yml` at the repository root:

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
<!-- clean-docs:begin actions -->
<!-- clean-docs:end actions -->
```

The source assignment may be a list of dictionaries or a dictionary whose values are records. Constructor calls are read as keyword records. clean-docs reads the syntax tree; the [security model](SECURITY_MODEL.md) owns the execution boundary.

### Legacy command pins

Manifest `type: claim` is the compatibility spelling for a command pin. It checks that an
allowlisted JSON command returns the configured expected value and that the document anchor exists.
It does not read the prose under that anchor. Use a generated scalar region when clean-docs should
own the bytes, or an accepted [source claim check](#source-claim-checks) for the bounded prose shapes
that the static detector supports.

## Supported binding surface

This table comes from the public capability registry:

<!-- clean-docs:begin supported-bindings -->
| binding | source | output | check |
| --- | --- | --- | --- |
| command pin (`type: claim`) | Allowlisted JSON command | Configured assertion plus an existing document anchor | Compare typed expected and observed values |
| region | Static Python, structured data, text, or paths | Table, list, scalar, or fenced text | Re-render and compare |
| symbol | Static path or Python symbol | Reference at a document anchor | Resolve the cited locator |
<!-- clean-docs:end supported-bindings -->

## Depth model

Keep the README focused on the point, first action, proof, and routing. Put procedures in guides and lookup material here. A binding keeps one canonical source for a fact; it does not require every fact to share one page.

Repositories do not configure a standard path. clean-docs bundles the policy pack compiled from [`STANDARD.md`](../STANDARD.md), and CI fails when the authored standard and compiled pack differ.

## Source claim checks

The boundary is narrow. Two prose shapes are in scope: numeric collection counts and identifier
rows in a table under a `Columns` heading. `claims` ranks a static Python source when the subject,
locator name, and repository path support the match. The detector proposes a relationship; it does
not pretend to understand arbitrary sentences or prove that both sides describe the same concept.

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
value remain the two values under comparison. `clean-docs claims` reports every accepted
relationship and bounded assessment candidates. A missing accepted locator fails closed.

Use `identifier-set` for a reference section whose `Columns` block should match the public keys of
a static Python mapping. Its locator ends in `#keys`, such as `USERS.fields#keys`. Leading
underscore keys remain implementation details and do not enter that public set.

`check --changed` evaluates an accepted relationship only when its document, source, or manifest
changed. Updating unrelated code does not create documentation work. Discovery does not repair
prose; update the documented value or the accepted relationship, then run `claims` and `check`
again.

## Manifest versions

Version 2 removes the `network` key from allowed commands because clean-docs does not provide an
operating-system network sandbox. Version 1 remains readable. If it contains `network: false`,
clean-docs marks that field as deprecated; it neither blocks nor counts network traffic. Run
`clean-docs migrate --write` to remove the field with a rollback backup.
