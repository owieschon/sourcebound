from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


EXPECTED = {
    "test_classification_complete_is_distinct_from_direct_protection",
    "test_selected_direct_policy_rejects_catalog_only_surface",
    "test_init_discloses_zero_direct_protection",
    "test_command_taxonomy_labels_core_and_experimental_surfaces",
    "test_static_verdict_never_starts_repository_process",
    "test_candidate_wheel_binds_release_ref",
    "test_runtime_review_receipt_requires_provenance",
}


def main() -> int:
    root = ET.parse(Path(sys.argv[1])).getroot()
    suite = root.find("testsuite") or root
    if int(suite.attrib.get("errors", "0")) or int(suite.attrib.get("skipped", "0")):
        raise SystemExit("contract suite had errors or skips")
    failed = {
        case.attrib.get("name", "")
        for case in suite.iter("testcase")
        if case.find("failure") is not None
    }
    if failed != EXPECTED or int(suite.attrib.get("failures", "0")) != len(EXPECTED):
        raise SystemExit(f"wrong frozen failures: {sorted(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
