# Compile bounded provider context

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this task when a provider needs selected source facts instead of whole documents. It produces a
content-addressed bundle that says why each item was kept or omitted, so a tight budget returns
unknown rather than silently dropping a required fact.
<!-- sourcebound:end purpose -->

**[Create the request](#create-the-request)**.

## Create the request

<!-- sourcebound:allow section-length reason="The field reference is linked; the complete request builder remains one runnable unit" -->

The request pins its own bytes and every selected source to one repository commit. It also records
the byte budget, source path and line range, evidence authority, relationship, rank, and whether
each item is required. Create `.sourcebound/context-request.json` from the repository's current
README:

```bash
mkdir -p .sourcebound
python3 - <<'PY'
import json
import subprocess
from pathlib import Path

readme = subprocess.check_output(
    ["git", "show", "HEAD:README.md"], text=True
).splitlines()
if not readme:
    raise SystemExit("README.md must be tracked and nonempty")
request = {
    "schema": "sourcebound.context-request.v2",
    "budget_bytes": 4096,
    "items": [{
        "id": "repository-opener",
        "kind": "fact",
        "path": "README.md",
        "start_line": 1,
        "end_line": min(12, len(readme)),
        "authority": "repository-doc",
        "relationship": "repository orientation",
        "reason": "defines the repository for this task",
        "rank": 10,
        "required": True,
        "instruction": False,
    }],
}
Path(".sourcebound/context-request.json").write_text(
    json.dumps(request, indent=2) + "\n",
    encoding="utf-8",
)
PY
```

The request is data. `instruction: false` prevents README prose from gaining instruction authority.
Review and commit it with the source state it selects:

```bash
git diff -- .sourcebound/context-request.json
git add .sourcebound/context-request.json
git commit -m "docs: pin context request"
```

Compilation rejects an untracked or modified request. An `accepted-policy` item can receive
instruction authority only when its pinned source document carries an active
`sourcebound:policy register-v2` marker.

## Compile it

Compile the saved request without invoking a provider:

```bash
sourcebound context compile \
  --request .sourcebound/context-request.json \
  --format json
```

Exit `0` returns a `sourcebound.context-bundle.v2` object with `"status": "current"`.

## Verify the bundle

Verify the schema and status from a fresh compilation:

```bash
sourcebound context compile \
  --request .sourcebound/context-request.json \
  --format json |
python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["schema"] == "sourcebound.context-bundle.v2" and p["status"] == "current"'
```

The result records the pinned request path and SHA-256, then lists included and excluded items with
reasons. Required items are selected first; within the required and optional classes, direct
evidence outranks repository prose. A source-verified accepted policy can carry instruction
authority; ordinary documentation remains data even when its text resembles a prompt. The
[context request reference](REFERENCE.md#context-request) owns the full field and authority
contract.

## Budget failure

If required evidence does not fit, the bundle reports `unknown` and the command exits `2`. Optional
items may be excluded only with a recorded reason. Compilation is lexical and source-addressed; it
does not use semantic retrieval or a vector index.

Use [evaluation](EVALUATION.md) to score what a provider does with the compiled context.
