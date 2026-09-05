"""Offline, clean-checkout replay of the ryankanno/cookiecutter-py PR #660 default-value bug.

Historical case (selected after the fact, for this repository's own test suite):
ryankanno/cookiecutter-py PR #660 corrected three README.md config-variable defaults
that had drifted from cookiecutter.json's actual defaults (y -> n, for
should_upload_coverage_to_codecov, should_publish_to_testpypi, should_publish_to_pypi).
See fixtures/ for the frozen, MIT-licensed upstream inputs and their provenance.

This script does not claim general accuracy or superior discovery over a plain
regex+JSON check -- both find the same three wrong claims on the same original
inputs, see step 2. What Sourcebound adds is a bounded, byte-preserving repair:
declared inline spans get corrected in place, everything else in the document is
untouched, and the check is immediately repeatable. No network access, no
subprocess execution, and no model calls happen anywhere in this script.

Run: python examples/cookiecutter-defaults-repair/replay.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sourcebound.engine import drive, evaluate  # noqa: E402
from sourcebound.errors import ConfigurationError, ExtractionError, RegionError  # noqa: E402
from sourcebound.regions import replace_region  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
UPSTREAM_README = FIXTURES / "upstream-README.md"
UPSTREAM_README_FIXED = FIXTURES / "upstream-README-fixed.md"
UPSTREAM_JSON = FIXTURES / "cookiecutter.json"
UPSTREAM_LICENSE = FIXTURES / "LICENSE"

EXPECTED_README_SHA256 = (
    "89b21a210d40a532767f0aee4b8eb95134b8077f10ba79f76bc4ccddfc881442"
)
EXPECTED_JSON_SHA256 = (
    "0dc48fe4682188e7a1feb9908a4ad886352cd08867c0fbe7a30c19a19a34adb8"
)

# All 13 default-value claims in the README, in document order. This list is
# manually annotated setup, not discovered: the case selection and the claim
# count both come from reading the fixed upstream inputs by hand.
DEFAULT_KEYS = [
    "project_license",
    "version",
    "python_version",
    "should_use_direnv",
    "should_create_author_files",
    "should_install_github_dependabot",
    "should_automerge_autoapprove_github_dependabot",
    "should_install_github_actions",
    "should_upload_coverage_to_codecov",
    "should_publish_to_testpypi",
    "should_publish_to_pypi",
    "should_publish_to_github_packages",
    "should_attach_to_github_release",
]
KNOWN_WRONG_KEYS = {
    "should_upload_coverage_to_codecov",
    "should_publish_to_testpypi",
    "should_publish_to_pypi",
}

MANIFEST_TEMPLATE = """\
version: 1
bindings:
{bindings}
"""

BINDING_TEMPLATE = """\
  - id: {key}
    type: region
    doc: README.md
    region: {key}
    extractor: json
    source:
      path: cookiecutter.json
      pointer: /{key}
    renderer: inline-scalar
"""


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_frozen_inputs() -> None:
    observed_readme = _sha256(UPSTREAM_README)
    observed_json = _sha256(UPSTREAM_JSON)
    if observed_readme != EXPECTED_README_SHA256:
        raise SystemExit(
            f"frozen upstream README changed: expected {EXPECTED_README_SHA256}, "
            f"got {observed_readme}"
        )
    if observed_json != EXPECTED_JSON_SHA256:
        raise SystemExit(
            f"frozen upstream cookiecutter.json changed: expected {EXPECTED_JSON_SHA256}, "
            f"got {observed_json}"
        )


def _baseline_regex_json_check(readme_text: str, config: dict) -> set[str]:
    """A minimal regex+JSON assertion, mirroring the check PR660 itself added.

    This is the comparison point, not a component Sourcebound depends on: it
    proves the bug is independently detectable without Sourcebound, so
    Sourcebound's contribution here is the bounded repair, not discovery.
    """
    wrong = set()
    for key in DEFAULT_KEYS:
        match = re.search(rf"`{re.escape(key)}`[^\n]*\(default: ([^)\n]*)\)", readme_text)
        if match is None:
            raise SystemExit(f"baseline check: {key} default claim not found in README")
        if match.group(1) != str(config[key]):
            wrong.add(key)
    return wrong


def _insert_markers(readme_text: str) -> tuple[str, int]:
    """Explicitly counted setup: wrap each of the 13 existing default tokens
    with same-line sourcebound markers, changing no other byte."""
    marked = readme_text
    inserted = 0
    for key in DEFAULT_KEYS:
        pattern = re.compile(rf"(`{re.escape(key)}`[^\n]*\(default: )([^)\n]*)(\))")
        matches = pattern.findall(marked)
        if len(matches) != 1:
            raise SystemExit(f"setup: expected exactly one default claim for {key}")
        marked, count = pattern.subn(
            rf"\g<1><!-- sourcebound:begin {key} -->\g<2><!-- sourcebound:end {key} -->\g<3>",
            marked,
        )
        assert count == 1
        inserted += 1
    return marked, inserted


def _strip_markers(readme_text: str) -> str:
    stripped = readme_text
    for key in DEFAULT_KEYS:
        stripped = stripped.replace(f"<!-- sourcebound:begin {key} -->", "")
        stripped = stripped.replace(f"<!-- sourcebound:end {key} -->", "")
    return stripped


def _demonstrate_negative_paths(tmp_root: Path) -> None:
    """Negative proof: malformed setups fail loudly and leave documents untouched."""
    document = "<!-- sourcebound:begin flag -->y<!-- sourcebound:begin flag -->\n"
    try:
        replace_region(document, "flag", "n", inline=True)
    except RegionError:
        pass
    else:
        raise SystemExit("negative proof failed: duplicate begin marker was not rejected")

    manifest_path = tmp_root / ".sourcebound.yml"
    bad_manifest = MANIFEST_TEMPLATE.format(
        bindings=BINDING_TEMPLATE.format(key="does_not_exist")
    )
    manifest_path.write_text(bad_manifest, encoding="utf-8")
    try:
        evaluate(tmp_root, manifest_path)
    except (ConfigurationError, ExtractionError):
        pass
    else:
        raise SystemExit("negative proof failed: missing JSON pointer was not rejected")


def main() -> None:
    _verify_frozen_inputs()
    config = json.loads(UPSTREAM_JSON.read_text(encoding="utf-8"))
    upstream_readme_text = UPSTREAM_README.read_text(encoding="utf-8")

    baseline_wrong = _baseline_regex_json_check(upstream_readme_text, config)
    print(f"1. Baseline regex+JSON check on frozen originals: {len(baseline_wrong)} wrong")
    if baseline_wrong != KNOWN_WRONG_KEYS:
        raise SystemExit(f"unexpected baseline result: {sorted(baseline_wrong)}")

    with tempfile.TemporaryDirectory(prefix="sourcebound-cookiecutter-replay-") as tmp:
        tmp_root = Path(tmp)
        marked_readme, inserted = _insert_markers(upstream_readme_text)
        assert inserted == len(DEFAULT_KEYS) == 13
        (tmp_root / "README.md").write_text(marked_readme, encoding="utf-8")
        shutil.copy(UPSTREAM_JSON, tmp_root / "cookiecutter.json")
        shutil.copy(UPSTREAM_LICENSE, tmp_root / "LICENSE")
        print(f"2. Setup: inserted {inserted} declared inline-scalar markers into a working copy")

        manifest_text = MANIFEST_TEMPLATE.format(
            bindings="".join(BINDING_TEMPLATE.format(key=key) for key in DEFAULT_KEYS)
        )
        manifest_path = tmp_root / ".sourcebound.yml"
        manifest_path.write_text(manifest_text, encoding="utf-8")

        results = evaluate(tmp_root, manifest_path)
        changed = {result.binding_id for result in results if result.changed}
        unchanged = {result.binding_id for result in results} - changed
        print(f"3. Sourcebound audit: {len(changed)} wrong, {len(unchanged)} unchanged")
        if changed != KNOWN_WRONG_KEYS or len(unchanged) != 10:
            raise SystemExit(f"unexpected drift result: changed={sorted(changed)}")

        drive(tmp_root, manifest_path)
        repaired_marked = (tmp_root / "README.md").read_text(encoding="utf-8")
        repaired = _strip_markers(repaired_marked)
        print("4. Drove the repair and stripped the inserted markers")

        expected = UPSTREAM_README_FIXED.read_text(encoding="utf-8")
        if repaired != expected:
            raise SystemExit("repaired README does not match the upstream fixed README byte-for-byte")
        print("5. Repaired README matches the upstream fixed README byte-for-byte")

        _demonstrate_negative_paths(tmp_root)
        print("6. Negative-path setups (duplicate marker, missing pointer) failed clearly")

    print(f"7. Frozen originals were never modified: {UPSTREAM_README}, {UPSTREAM_JSON}")


if __name__ == "__main__":
    main()
