from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from clean_docs.cli import main
from clean_docs.doctor import diagnose
from clean_docs.errors import ConfigurationError
from clean_docs.residue import load_residue_config, scan_residue


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _track(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)


def test_scans_configured_tokens_paths_and_generated_artifacts(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    digest = hashlib.sha256(b"foreign-token").hexdigest()
    (root / ".clean-docs-residue.yml").write_text(f"""\
version: 1
rules:
  - id: foreign-context
    token_sha256: {digest}
    include: ["*"]
    reason: This token belongs to another project.
exclude:
  - pattern: docs/archive/**
    reason: Archived fixtures are intentionally outside the active surface.
""")
    (root / "README.md").write_text(
        "# Product\n\nforeign-token\n\n/" + "Users/alicebuild/private/file.txt\n"
    )
    cache = root / "src/__pycache__"
    cache.mkdir(parents=True)
    (cache / "module.pyc").write_bytes(b"compiled")
    archive = root / "docs/archive"
    archive.mkdir(parents=True)
    (archive / "REFERENCE.md").write_text("foreign-token\n")
    _track(root)

    findings = scan_residue(root)

    assert {(finding.rule, finding.doc, finding.line) for finding in findings} == {
        ("cross-project-residue", "README.md", 3),
        ("local-path-residue", "README.md", 5),
        ("generated-artifact", "src/__pycache__/module.pyc", 1),
    }


def test_rejects_weak_or_unknown_residue_configuration(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs-residue.yml"
    path.write_text("version: 1\nrules: []\nunknown: true\n")
    with pytest.raises(ConfigurationError, match="unknown key"):
        load_residue_config(path)


def test_scans_current_worktree_content_before_it_is_staged(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    digest = hashlib.sha256(b"foreign-token").hexdigest()
    (root / ".clean-docs-residue.yml").write_text(f"""\
version: 1
rules:
  - id: foreign-context
    token_sha256: {digest}
    include: ["*"]
    reason: This token belongs to another project.
""")
    readme = root / "README.md"
    readme.write_text("# Product\n\nCurrent documentation.\n")
    _track(root)
    readme.write_text("# Product\n\nforeign-token\n")

    findings = scan_residue(root)

    assert [(finding.rule, finding.doc, finding.line) for finding in findings] == [
        ("cross-project-residue", "README.md", 3),
    ]


def test_v2_uses_private_local_rules_without_publishing_token_material(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".clean-docs-residue.yml").write_text("version: 2\nexclude: []\n")
    local = root / ".clean-docs-residue.local.yml"
    local.write_text("version: 1\nrules:\n  - id: private-context\n    token: foreign-token\n    include: ['*']\n")
    local.chmod(0o600)
    (root / "README.md").write_text("# Product\n\nforeign-token\n")
    _track(root)

    findings = scan_residue(root)

    assert [(finding.rule, finding.doc, finding.line) for finding in findings] == [
        ("cross-project-residue", "README.md", 3),
    ]


def test_v2_rejects_published_residue_rules(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs-residue.yml"
    path.write_text("version: 2\nrules: []\nexclude: []\n")

    with pytest.raises(ConfigurationError, match="permits exclusions only"):
        load_residue_config(path)


def test_private_residue_status_is_redacted_and_initializer_is_restricted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)

    assert main(["--root", str(root), "residue", "status"]) == 0
    assert "inactive" in capsys.readouterr().out
    assert main(["--root", str(root), "residue", "init-local"]) == 0
    local = root / ".clean-docs-residue.local.yml"
    assert local.stat().st_mode & 0o777 == 0o600
    local.write_text("version: 1\nrules:\n  - id: private-context\n    token: private-value\n    include: ['*']\n")
    local.chmod(0o600)
    assert main(["--root", str(root), "residue", "status"]) == 0
    output = capsys.readouterr().out
    assert "active" in output
    assert "private-value" not in output


def test_local_path_rule_ignores_placeholders_and_embedded_route_names(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Paths\n\n"
        "/Users/<you>/project\n"
        "/Users/username/project\n"
        "/Users/YOUR_USERNAME/project\n"
        "/Users/me/project\n"
        "/home/user/project\n"
        "/Accounts/Users/Relationships\n"
        "/" + "Users/alicebuild/private/project\n"
    )
    _track(root)

    findings = scan_residue(root)

    assert [(finding.rule, finding.line) for finding in findings] == [
        ("local-path-residue", 9),
    ]


def test_excludes_versioned_independent_reader_evidence_verbatim(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / ".clean-docs-residue.yml").write_text("""\
version: 1
exclude:
  - pattern: .clean-docs/reader-trials*/**
    reason: Independent reader evidence preserves observed paths verbatim.
rules: []
""")
    evidence = root / ".clean-docs/reader-trials-v1.1/reader/run-tutorial.txt"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("workspace: /" + "Users/example/private/fixture\n")
    _track(root)

    assert scan_residue(root) == []


def test_invalid_policy_is_a_stable_audit_and_doctor_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("# Product\n")
    (root / ".clean-docs-residue.yml").write_text(
        "version: 1\nrules: []\nunknown: true\n"
    )
    _track(root)

    exit_code = main(["--root", str(root), "audit"])
    checks = diagnose(root, root / ".clean-docs.yml")

    assert exit_code == 2
    assert "unknown key" in capsys.readouterr().err
    documentation = next(check for check in checks if check.name == "documentation-audit")
    assert documentation.ok is False
    assert "unknown key" in documentation.detail
