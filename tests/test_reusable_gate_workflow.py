from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_reusable_gate_installs_and_invokes_the_sourcebound_runtime() -> None:
    workflow = (ROOT / ".github/workflows/reusable-sourcebound.yml").read_text()

    assert "check_name:" in workflow
    assert "name: ${{ inputs.check_name }}" in workflow
    assert '"sourcebound @ git+https://github.com/owieschon/sourcebound.git@${SOURCEBOUND_PACKAGE_REF}"' in workflow
    assert 'python3 -I -m sourcebound --root "$GITHUB_WORKSPACE" verdict' in workflow
    assert "from sourcebound.verdict import render_verdict_payload_sarif" in workflow
    assert '"schema": "sourcebound.action-run.v2"' in workflow
