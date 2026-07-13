from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from clean_docs.engine import evaluate


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "guides").mkdir(parents=True)
    (root / "examples").mkdir()
    (root / "guides/start.md").write_text("# Start\n")
    (root / "examples/settings.ini").write_text("enabled=true\n")
    (root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
    (root / "commands.yaml").write_text("commands:\n  - name: audit\n    writes: false\n")
    (root / "README.md").write_text("""\
# Fixture

<!-- clean-docs:begin version -->
stale
<!-- clean-docs:end version -->

<!-- clean-docs:begin guides -->
stale
<!-- clean-docs:end guides -->

<!-- clean-docs:begin commands -->
stale
<!-- clean-docs:end commands -->

<!-- clean-docs:begin example -->
stale
<!-- clean-docs:end example -->
""")
    (root / ".clean-docs.yml").write_text("""\
version: 1
bindings:
  - id: version
    type: region
    doc: README.md
    region: version
    extractor: structured-data
    source: {path: pyproject.toml, pointer: /project/version}
    renderer: scalar
  - id: guides
    type: region
    doc: README.md
    region: guides
    extractor: path
    source: {glob: guides/*.md}
    renderer: markdown-list
  - id: commands
    type: region
    doc: README.md
    region: commands
    extractor: structured-data
    source: {path: commands.yaml, pointer: /commands}
    renderer: markdown-table
    columns: [name, writes]
  - id: example
    type: region
    doc: README.md
    region: example
    extractor: file
    source: {path: examples/settings.ini}
    renderer: fenced-text
    language: ini
""")
    return root


def test_static_extractors_render_and_remain_ref_pure(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    driven = _run(root, "drive")
    assert driven.returncode == 0, driven.stderr
    readme = (root / "README.md").read_text()
    assert "1.2.3" in readme
    assert "- guides/start.md" in readme
    assert "| audit | false |" in readme
    assert "```ini\nenabled=true\n```" in readme

    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
         "user.email=fixture@example.test", "commit", "-qm", "baseline"],
        check=True,
    )
    baseline = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    (root / "pyproject.toml").write_text('[project]\nversion = "2.0.0"\n')
    (root / "guides/advanced.md").write_text("# Advanced\n")
    before = (root / "pyproject.toml").read_text()
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
         "user.email=fixture@example.test", "commit", "-qm", "changed"],
        check=True,
    )
    changed_ref = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    assert _run(root, "check").returncode == 1
    pinned = _run(root, "check", "--ref", baseline)
    assert pinned.returncode == 0, pinned.stderr
    forward = (
        evaluate(root, root / ".clean-docs.yml", ref=baseline),
        evaluate(root, root / ".clean-docs.yml", ref=changed_ref),
    )
    reverse = (
        evaluate(root, root / ".clean-docs.yml", ref=changed_ref),
        evaluate(root, root / ".clean-docs.yml", ref=baseline),
    )
    assert forward[0] == reverse[1]
    assert forward[1] == reverse[0]
    assert "1.2.3" in forward[0][0].expected
    assert "2.0.0" in forward[1][0].expected
    assert (root / "pyproject.toml").read_text() == before
