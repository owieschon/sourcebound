# Catch a lying doc

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
This tutorial is for maintainers who want to see one source-bound fact fail and recover in a disposable repository. It turns an easy-to-miss command rename into a named check failure, a region-only repair, and a verified projection using an installed sourcebound release.
<!-- sourcebound:end purpose -->

**[Install the stable release](../INSTALL.md#install-the-latest-stable-release)**, then
build the disposable repository below.

Success appears in the [outcome receipt](../SUPPORT.md#record-local-outcomes) after the last
command: its `ok` field reads `true`.

The source will move first. The bound table cannot keep pretending it did not.

You will build Moonbase Status, a tiny operator guide whose public action table comes from a
Python literal. No repository code is imported or executed. The [manifest page](../REFERENCE.md)
lists every binding, and the [install guide](../INSTALL.md) covers other install paths.

## Before you begin

Install a stable sourcebound artifact in an isolated environment and confirm `sourcebound --version` works. The [offline procedure](../INSTALL.md#install-without-package-index-access) is the path used to test this tutorial. You also need Git and Python 3.10 or newer.

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

<!-- sourcebound:purpose -->
Use this guide when a habitat operator needs the current public actions. It keeps the action table tied to source so a renamed command cannot remain plausible in the guide.
<!-- sourcebound:end purpose -->

## Operator actions

<!-- sourcebound:begin status-actions -->
<!-- sourcebound:end status-actions -->
MD
cat > .sourcebound.yml <<'YAML'
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
sourcebound drive
sourcebound project
sourcebound check
sourcebound verify
git add .sourcebound.yml README.md llms.txt src/actions.py
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
sourcebound check
```

The final command exits `1` and names `status-actions`. That failure is the lesson: the old prose still reads well, but it no longer gets to pass as current.

## 4. Repair and verify

Repair the bound region, inspect its exact diff, refresh the projection, and run the final gate:

```bash
sourcebound drive
git diff -- README.md
sourcebound project
sourcebound check
sourcebound verify
```

`drive` changes the table row from `report` to `publish` without rewriting the surrounding prose. `project` updates the page digest in `llms.txt`. The last two commands exit `0`.

The release-tested fixture records the same state changes:

<!-- sourcebound:begin tutorial-outcomes -->
| moment | command | exit | meaning |
| --- | --- | --- | --- |
| Protected baseline | sourcebound check | 0 | The bound page matches source. |
| Source changed alone | sourcebound check | 1 | The status-actions binding is stale. |
| Declared region repaired | sourcebound drive | 0 | Only the bound region changes. |
| Projection refreshed | sourcebound project | 0 | llms.txt receives the repaired page digest. |
| Repository verified | sourcebound verify | 0 | Bindings and projections are current. |
<!-- sourcebound:end tutorial-outcomes -->

You have now seen the full loop. Read [the deterministic seam](deep-dive-the-deterministic-seam.md) to understand why a model can help with wording without gaining authority over this result.
