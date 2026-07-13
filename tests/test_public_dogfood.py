from pathlib import Path

from clean_docs.manifest import load_manifest
from scripts.dogfood_public_repos import CASES


def test_public_dogfood_contracts_are_strict_and_pinned(tmp_path: Path) -> None:
    assert {case.name for case in CASES} == {"ultra-csm", "agent-governance-lab"}
    for case in CASES:
        assert len(case.commit) == 40
        assert case.url.startswith("https://github.com/")
        manifest = tmp_path / f"{case.name}.yml"
        manifest.write_text(case.manifest)
        binding = load_manifest(manifest).bindings[0]
        assert binding.source.path == case.source
        assert case.before != case.after
