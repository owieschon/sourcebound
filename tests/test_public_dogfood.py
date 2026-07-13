from pathlib import Path

from clean_docs.manifest import load_manifest
from clean_docs.models import RegionBinding, SymbolBinding
from scripts.dogfood_bootstrap_repos import CASES as BOOTSTRAP_CASES
from scripts.dogfood_public_repos import CASES


def test_public_dogfood_contracts_are_strict_and_pinned(tmp_path: Path) -> None:
    assert {case.name for case in CASES} == {"ultra-csm", "agent-governance-lab"}
    assert {case.binding_type for case in CASES} == {"region", "symbol"}
    for case in CASES:
        assert len(case.commit) == 40
        assert case.url.startswith("https://github.com/")
        manifest = tmp_path / f"{case.name}.yml"
        manifest.write_text(case.manifest)
        binding = load_manifest(manifest).bindings[0]
        assert isinstance(binding, (RegionBinding, SymbolBinding))
        assert (
            "region" if isinstance(binding, RegionBinding) else "symbol"
        ) == case.binding_type
        assert binding.source.path == case.source
        assert case.before != case.after


def test_bootstrap_dogfood_contracts_are_cross_language_and_pinned() -> None:
    assert {case.name for case in BOOTSTRAP_CASES} == {"sampleproject", "yocto-queue"}
    assert {case.language for case in BOOTSTRAP_CASES} == {"Python", "TypeScript"}
    assert {case.readme for case in BOOTSTRAP_CASES} == {"README.md", "readme.md"}
    for case in BOOTSTRAP_CASES:
        assert len(case.commit) == 40
        assert case.url.startswith("https://github.com/")
        assert case.evidence_adapter
