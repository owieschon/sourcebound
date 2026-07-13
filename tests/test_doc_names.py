from pathlib import Path

from scripts.check_doc_names import scan


def test_finds_blocked_name_in_documentation(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("clau" + "de code")
    findings = scan(tmp_path)
    assert [(path.as_posix(), line) for path, line, _ in findings] == [("README.md", 1)]


def test_ignores_source_files_and_git_data(tmp_path: Path) -> None:
    (tmp_path / "example.py").write_text("clau" + "de")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/history.txt").write_text("clau" + "de")
    assert scan(tmp_path) == []
