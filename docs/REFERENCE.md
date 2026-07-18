# Manifest reference

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
This reference defines the manifest fields and binding surfaces that clean-docs accepts. Use it when you need to protect a repository fact without guessing where that fact belongs.
<!-- clean-docs:end purpose -->

**[Create a binding from the runnable tutorial](learn/tutorial-catch-a-lying-doc.md)**.

Confirm the result with [`clean-docs check` and `clean-docs verify`](CLI.md).

## Binding types

This table comes from the manifest validator:

<!-- clean-docs:begin manifest-reference -->
| binding | required | verifies |
| --- | --- | --- |
| region | id, type, doc, region, extractor, source, renderer | Generated content matches source evidence |
| claim | id, type, doc, anchor, command, assertion | Observed command value matches the assertion |
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

## Supported binding surface

This table comes from the public capability registry:

<!-- clean-docs:begin supported-bindings -->
| binding | source | output | check |
| --- | --- | --- | --- |
| claim | Allowlisted JSON command | Assertion at a document anchor | Compare typed expected and observed values |
| region | Static Python, structured data, text, or paths | Table, list, scalar, or fenced text | Re-render and compare |
| symbol | Static path or Python symbol | Reference at a document anchor | Resolve the cited locator |
<!-- clean-docs:end supported-bindings -->

## Depth model

Keep the README focused on the point, first action, proof, and routing. Put procedures in guides and lookup material here. A binding keeps one canonical source for a fact; it does not require every fact to share one page.

Repositories do not configure a standard path. clean-docs bundles the policy pack compiled from [`STANDARD.md`](../STANDARD.md), and CI fails when the authored standard and compiled pack differ.
