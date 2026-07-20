from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


MANIFEST = """\
version: 1
bindings:
  - id: overview
    type: region
    doc: README.md
    region: overview
    extractor: file
    source: {path: source.txt}
    renderer: scalar
projections:
  llms_txt:
    output: llms.txt
    title: Fixture documentation
    summary: Canonical fixture pages and their verified bindings.
  bundles:
    - id: contributor
      output: .sourcebound/context/contributor.md
      include: [README.md]
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    source = Path(__file__).parents[1] / "src"
    environment["PYTHONPATH"] = str(source) + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "source.txt").write_text("Bound overview\n")
    (root / "README.md").write_text(
        "# Fixture\n\n[Limits](#limits)\n\n"
        "<!-- sourcebound:begin overview -->\nBound overview\n"
        "<!-- sourcebound:end overview -->\n\n## Limits\n\nOnly declared bindings are checked.\n"
    )
    (root / ".sourcebound.yml").write_text(MANIFEST)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "fixture"],
        check=True,
    )
    return root


def test_single_source_projection_changes_every_affected_output(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    first = _run(root, "project")
    assert first.returncode == 0, first.stderr
    llms_before = (root / "llms.txt").read_text()
    bundle_before = (root / ".sourcebound/context/contributor.md").read_text()
    readme_before = (root / "README.md").read_text()
    readme_digest = hashlib.sha256(readme_before.encode()).hexdigest()
    assert f"sha256: {readme_digest}" in llms_before
    assert f"Content sha256: `{readme_digest}`" in bundle_before
    assert "[README.md](../../README.md)" in bundle_before
    assert readme_before.rstrip() in bundle_before
    assert "Source ref: `" in bundle_before
    assert "Corpus sha256: `" in bundle_before

    (root / "README.md").write_text(readme_before + "\nA canonical task note.\n")
    second = _run(root, "project")
    assert second.returncode == 0, second.stderr
    assert (root / "llms.txt").read_text() != llms_before
    assert (root / ".sourcebound/context/contributor.md").read_text() != bundle_before
    assert "A canonical task note." in (root / ".sourcebound/context/contributor.md").read_text()


def test_stale_projection_fails_check_and_project_repairs_it(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert _run(root, "project").returncode == 0
    assert _run(root, "check").returncode == 0
    (root / "README.md").write_text((root / "README.md").read_text() + "\nNew note.\n")

    stale = _run(root, "check")
    assert stale.returncode == 1
    assert "[drift] projection:llms.txt" in stale.stdout
    assert "[drift] projection:.sourcebound/context/contributor.md" in stale.stdout

    assert _run(root, "project").returncode == 0
    assert _run(root, "project", "--check").returncode == 0
    assert _run(root, "check").returncode == 0


def test_project_rejects_broken_canonical_anchor(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    readme = (root / "README.md").read_text().replace("#limits", "#missing")
    (root / "README.md").write_text(readme)

    result = _run(root, "project")

    assert result.returncode == 2
    assert "broken projection anchor: README.md -> #missing" in result.stderr
    assert not (root / "llms.txt").exists()


def test_project_accepts_an_existing_repository_directory_link(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "schemas").mkdir()
    (root / "schemas/item.json").write_text("{}\n")
    readme = (root / "README.md").read_text()
    (root / "README.md").write_text(readme + "\n[Schema directory](schemas/)\n")

    result = _run(root, "project")

    assert result.returncode == 0, result.stderr
    assert (root / "llms.txt").is_file()
