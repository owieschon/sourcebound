from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sourcebound.cli import main
from sourcebound.changed import check_changed


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(root), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "-qm", message,
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _region_repository(tmp_path: Path) -> Path:
    root = tmp_path / "region-repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "src/commands.py").write_text(
        'COMMANDS = [{"name": "serve", "job": "Run the service"}]\n'
    )
    (root / "README.md").write_text(
        "# Service\n\n<!-- sourcebound:begin commands -->\n"
        "<!-- sourcebound:end commands -->\n"
    )
    (root / ".sourcebound.yml").write_text("""\
version: 1
bindings:
  - id: commands
    type: region
    doc: README.md
    region: commands
    extractor: python-literal
    source: {path: src/commands.py, symbol: COMMANDS}
    renderer: markdown-table
    columns: [name, job]
""")
    assert main(["--root", str(root), "derive", "--write"]) == 0
    return root


def _symbol_repository(tmp_path: Path) -> Path:
    root = tmp_path / "symbol-repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "src/api.py").write_text(
        "def public_api():\n    return True\n\n"
        "def _helper():\n    return 1\n"
    )
    (root / "README.md").write_text(
        "# Service\n\n## API\n\nThe public API is defined in `src/api.py`.\n"
    )
    (root / ".sourcebound.yml").write_text("""\
version: 1
bindings:
  - id: public-api
    type: symbol
    doc: README.md
    anchor: api
    source: {path: src/api.py, symbol: public_api}
""")
    return root


def test_changed_bound_evidence_has_stable_required_finding_and_sarif(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _region_repository(tmp_path)
    capsys.readouterr()
    base = _commit(root, "base")
    source = root / "src/commands.py"
    source.write_text(
        'COMMANDS = [{"name": "serve", "job": "Run the service"}, '
        '{"name": "inspect", "job": "Inspect state"}]\n'
    )
    head = _commit(root, "add command")

    args = [
        "--root", str(root), "check", "--changed", "--base", base, "--head", head,
        "--format", "json",
    ]
    assert main(args) == 1
    first = json.loads(capsys.readouterr().out)
    assert first["gaps"] == []
    assert first["dependencies"] == {"commands": ["src/commands.py"]}
    assert len(first["required"]) == 1
    finding = first["required"][0]
    assert finding["rule"] == "binding-drift"
    assert finding["repair"] == "sourcebound drive --binding commands"

    assert main(args) == 1
    second = json.loads(capsys.readouterr().out)
    assert second == first

    sarif_args = args[:-1] + ["sarif"]
    assert main(sarif_args) == 1
    sarif = json.loads(capsys.readouterr().out)
    result = sarif["runs"][0]["results"][0]
    assert result["partialFingerprints"]["sourceboundFindingId"] == finding["id"]
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "README.md"


def test_changed_new_public_surface_is_a_separate_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text() + '\nsub.add_parser("serve")\n')
    head = _commit(root, "add command")

    assert main([
        "--root", str(root), "check", "--changed", "--base", base, "--head", head,
        "--format", "json",
    ]) == 1

    result = json.loads(capsys.readouterr().out)
    assert result["required"] == []
    assert result["dependencies"] == {"public-api": ["src/api.py"]}
    assert len(result["gaps"]) == 1
    assert result["gaps"][0]["rule"] == "new-public-surface"
    assert "serve" in result["gaps"][0]["message"]


def test_changed_link_line_move_is_not_a_public_surface_gap(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    readme = root / "README.md"
    readme.write_text(
        readme.read_text() + "\nSee [the source](src/api.py).\n"
    )
    base = _commit(root, "base")
    readme.write_text(
        readme.read_text().replace(
            "\nSee [the source]", "\nRead this first.\n\nSee [the source]"
        )
    )
    head = _commit(root, "move link down")

    report = check_changed(
        root, root / ".sourcebound.yml", base=base, head=head
    )

    assert report.ok
    assert report.required == ()
    assert report.gaps == ()


def test_changed_first_install_accepts_derived_repository_overview(
    tmp_path: Path,
) -> None:
    root = tmp_path / "existing-repository"
    source = root / "src/package"
    source.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for index in range(40):
        (source / f"module_{index}.py").write_text(
            f"def surface_{index}():\n    return {index}\n"
        )
    (root / "README.md").write_text("# Existing repository\n")
    base = _commit(root, "existing repository")

    (root / "README.md").write_text(
        "# Existing repository\n\n## Repository surface\n\n"
        "<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    (root / ".sourcebound.yml").write_text("""\
version: 1
bindings:
  - id: repository-surface
    type: region
    doc: README.md
    region: repository-surface
    extractor: repository-overview
    source: {path: .}
    renderer: markdown-fragment
""")
    assert main(["--root", str(root), "derive", "--write"]) == 0
    head = _commit(root, "install sourcebound")

    report = check_changed(root, root / ".sourcebound.yml", base=base, head=head)

    assert report.ok
    assert report.required == ()
    assert report.gaps == ()


def test_changed_private_refactor_stays_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return 1", "return 2"))
    head = _commit(root, "private refactor")

    assert main([
        "--root", str(root), "check", "--changed", "--base", base, "--head", head,
        "--format", "json",
    ]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["required"] == []
    assert result["gaps"] == []


def test_changed_reasoned_ignore_is_visible_and_stale_ignore_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    original = source.read_text()
    source.write_text(original + '\nsub.add_parser("internal")\n')
    identifier = "cli-command:src/api.py:internal"
    (root / ".sourcebound-ignore.yml").write_text(
        "version: 1\nignore:\n"
        f"  - id: {json.dumps(identifier)}\n"
        "    reason: This command is reserved for repository maintainers.\n"
    )
    head = _commit(root, "add ignored internal command")

    assert main([
        "--root", str(root), "check", "--changed", "--base", base, "--head", head,
        "--format", "json",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["gaps"] == []
    assert len(result["ignored"]) == 1
    assert result["ignored"][0]["source"] == "src/api.py"

    source.write_text(original)
    stale_head = _commit(root, "remove ignored command")
    assert main([
        "--root", str(root), "check", "--changed", "--base", head,
        "--head", stale_head,
    ]) == 2
    assert "names an unknown inventory id" in capsys.readouterr().err


def test_changed_cache_reuses_base_and_preserves_normalized_output(tmp_path: Path) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return 1", "return 2"))
    head = _commit(root, "first private refactor")
    manifest = root / ".sourcebound.yml"

    first = check_changed(root, manifest, base=base, head=head)
    second = check_changed(root, manifest, base=base, head=head)

    assert (first.cache_hits, first.cache_misses) == (0, 2)
    assert (second.cache_hits, second.cache_misses) == (2, 0)
    assert first.as_dict() == second.as_dict()

    source.write_text(source.read_text().replace("return 2", "return 3"))
    changed_head = _commit(root, "second private refactor")
    changed = check_changed(root, manifest, base=base, head=changed_head)
    uncached = check_changed(
        root, manifest, base=base, head=changed_head, use_cache=False
    )

    assert (changed.cache_hits, changed.cache_misses) == (1, 1)
    assert changed.as_dict() == uncached.as_dict()


def test_changed_monorepo_project_selection_isolates_other_manifests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "monorepo"
    project_a = root / "packages/a"
    project_b = root / "packages/b"
    (project_a / "src").mkdir(parents=True)
    project_b.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (project_a / "src/api.py").write_text("def public_api():\n    return True\n")
    (project_a / "README.md").write_text("# A\n\n## API\n\nPublic API.\n")
    (project_a / ".sourcebound.yml").write_text("""\
version: 1
bindings:
  - id: public-api
    type: symbol
    doc: README.md
    anchor: api
    source: {path: src/api.py, symbol: public_api}
""")
    (project_b / ".sourcebound.yml").write_text("invalid: true\n")
    base = _commit(root, "base")
    (project_a / "src/api.py").write_text(
        "def public_api():\n    return True\n\nsub.add_parser(\"serve\")\n"
    )
    head = _commit(root, "change project a")

    assert main([
        "--root", str(root), "check", "--changed", "--base", base, "--head", head,
        "--project", "packages/a", "--format", "json",
    ]) == 1

    result = json.loads(capsys.readouterr().out)
    assert result["project"] == "packages/a"
    assert result["changed_files"] == ["packages/a/src/api.py"]
    assert len(result["gaps"]) == 1
    assert result["gaps"][0]["source"] == "packages/a/src/api.py"
