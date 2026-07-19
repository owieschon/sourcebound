from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    request = json.load(sys.stdin)
    Path("plugin-write-attempt.txt").write_text("discarded with the snapshot\n")
    operation = request["operation"]
    if operation == "extractor":
        source = Path(request["payload"]["source"])
        result = {"kind": "list", "value": source.read_text().splitlines()}
    elif operation == "discoverer":
        source = Path("facts.ext")
        kind = "cli-command" if Path("collision.ext").exists() else "extension-command"
        item_source = "cli.py" if Path("collision.ext").exists() else source.as_posix()
        result = {
            "items": [
                {
                    "kind": kind,
                    "name": "fixture",
                    "source": item_source,
                    "locator": "fixture",
                    "evidence": source.read_text(),
                }
            ]
        }
    elif operation == "renderer":
        result = {
            "content": "\n".join(
                f"- {item}" for item in request["payload"]["value"]
            )
        }
    elif operation == "policy":
        findings = []
        for doc, content in request["payload"]["documents"].items():
            if "FORBIDDEN" in content:
                findings.append(
                    {
                        "doc": doc,
                        "line": 1,
                        "rule": "fixture-forbidden",
                        "detail": "replace FORBIDDEN with a supported value",
                    }
                )
        result = {"findings": findings}
    else:
        raise SystemExit(f"unsupported fixture operation: {operation}")
    json.dump(
        {
            "schema": "sourcebound.plugin-response.v1",
            "api_version": 1,
            "result": result,
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
