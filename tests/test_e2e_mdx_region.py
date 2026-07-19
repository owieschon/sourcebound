from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]

MANIFEST = """\
version: 1
bindings:
  - id: actions
    type: region
    doc: docs/guide.mdx
    region: actions
    extractor: python-literal
    source:
      path: src/actions.py
      symbol: ACTIONS
    renderer: markdown-table
    columns: [name, tier]
"""

SOURCE_TWO = """\
ACTIONS = {
    "check": {"name": "check", "tier": 1},
    "drive": {"name": "drive", "tier": 2},
}
"""

SOURCE_THREE = SOURCE_TWO.replace(
    "}\n",
    '    "project": {"name": "project", "tier": 3},\n}\n',
)

MDX = """\
---
title: Action guide
---

import NeverRun from '../../outside.js'

# Action guide

<Callout tone="note">
The source owns this table.
</Callout>

{/* clean-docs:begin actions */}
| name | tier |
| --- | --- |
| check | 1 |
| drive | 2 |
{/* clean-docs:end actions */}

```md
{/* clean-docs:begin fake */}
[Missing](missing-inside-fence.md)
{/* clean-docs:end fake */}
```

Author-owned ending.
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def test_mdx_region_drifts_repairs_and_preserves_every_other_byte(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "src").mkdir()
    (root / ".clean-docs.yml").write_text(MANIFEST)
    (root / "src/actions.py").write_text(SOURCE_TWO)
    document = root / "docs/guide.mdx"
    document.write_text(MDX)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert _run(root, "check").returncode == 0
    assert _run(root, "audit").returncode == 0
    (root / "src/actions.py").write_text(SOURCE_THREE)

    stale = _run(root, "check")
    assert stale.returncode == 1
    assert "actions" in stale.stdout
    assert document.read_text() == MDX

    repaired = _run(root, "drive")
    assert repaired.returncode == 0
    updated = document.read_text()
    before_prefix, before_suffix = MDX.split("| check | 1 |\n| drive | 2 |")
    after_prefix, after_suffix = updated.split(
        "| check | 1 |\n| drive | 2 |\n| project | 3 |"
    )
    assert after_prefix == before_prefix
    assert after_suffix == before_suffix
    assert _run(root, "check").returncode == 0
    assert _run(root, "audit").returncode == 0
