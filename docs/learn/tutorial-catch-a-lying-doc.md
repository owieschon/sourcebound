# Catch a lying doc

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
This tutorial is for maintainers who want to see one source-bound fact fail and recover in a disposable repository. It turns an easy-to-miss command rename into a named check failure, a region-only repair, and a verified projection using an installed clean-docs release.
<!-- clean-docs:end purpose -->

**[Install the stable release](../INSTALL.md#install-the-latest-stable-release)**, then
build the disposable repository below.

Success appears in the [outcome receipt](../SUPPORT.md#record-local-outcomes) after the last
command: its `ok` field reads `true`.

The source will move first. The bound table cannot keep pretending it did not.

You will build Moonbase Status, a tiny operator guide whose public action table comes from a
Python literal. No repository code is imported or executed. The [manifest page](../REFERENCE.md)
lists every binding, and the [install guide](../INSTALL.md) covers other install paths.

## Before you begin

Install a stable clean-docs artifact in an isolated environment and confirm `clean-docs --version` works. The [offline procedure](../INSTALL.md#install-without-package-index-access) is the path used to test this tutorial. You also need Git and Python 3.10 or newer.

## 1. Build the fixture

Create an empty repository, its source-owned action, the page, and the binding manifest:

```bash
mkdir moonbase-status
cd moonbase-status
git init
mkdir src
cat > src/actions.py <<'PY'
ACTIONS = [
    {"command": "report", "job": "Send the current habitat status"},
]
PY
cat > README.md <<'MD'
# Moonbase Status

<!-- clean-docs:purpose -->
Use this guide when a habitat operator needs the current public actions. It keeps the action table tied to source so a renamed command cannot remain plausible in the guide.
<!-- clean-docs:end purpose -->

## Operator actions

<!-- clean-docs:begin status-actions -->
<!-- clean-docs:end status-actions -->
MD
cat > .clean-docs.yml <<'YAML'
version: 1
bindings:
  - id: status-actions
    type: region
    doc: README.md
    region: status-actions
    extractor: python-literal
    source: {path: src/actions.py, symbol: ACTIONS}
    renderer: markdown-table
    columns: [command, job]
projections:
  llms_txt:
    output: llms.txt
    title: Moonbase Status documentation
    summary: Source-bound operator documentation.
    include: [README.md]
YAML
```

## 2. Protect the baseline

Render the declared region, generate the projection, and verify the repository:

```bash
clean-docs drive
clean-docs project
clean-docs check
clean-docs verify
git add .clean-docs.yml README.md llms.txt src/actions.py
git commit -m "Protect operator actions"
```

The check exits `0`. The receipt reports `"ok": true`, and the README now contains the `report` row derived from `ACTIONS`.

## 3. Create honest drift

Rename the source command without touching the README:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path("src/actions.py")
path.write_text(path.read_text().replace('"report"', '"publish"'))
PY
clean-docs check
```

The final command exits `1` and names `status-actions`. That failure is the lesson: the old prose still reads well, but it no longer gets to pass as current.

## 4. Repair and verify

Repair the bound region, inspect its exact diff, refresh the projection, and run the final gate:

```bash
clean-docs drive
git diff -- README.md
clean-docs project
clean-docs check
clean-docs verify
```

`drive` changes the table row from `report` to `publish` without rewriting the surrounding prose. `project` updates the page digest in `llms.txt`. The last two commands exit `0`.

The release-tested fixture records the same state changes:

<!-- clean-docs:begin tutorial-outcomes -->
| moment | command | exit | meaning |
| --- | --- | --- | --- |
| Protected baseline | clean-docs check | 0 | The bound page matches source. |
| Source changed alone | clean-docs check | 1 | The status-actions binding is stale. |
| Declared region repaired | clean-docs drive | 0 | Only the bound region changes. |
| Projection refreshed | clean-docs project | 0 | llms.txt receives the repaired page digest. |
| Repository verified | clean-docs verify | 0 | Bindings and projections are current. |
<!-- clean-docs:end tutorial-outcomes -->

You have now seen the full loop. Read [the deterministic seam](deep-dive-the-deterministic-seam.md) to understand why a model can help with wording without gaining authority over this result.
