# Configure the optional init proposer

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this task when deterministic discovery has found candidate facts but a bounded provider should
choose draft inputs for the generated reference. It gives the provider proposal authority only, so
malformed or unsupported selections fail before Sourcebound writes the baseline.
<!-- sourcebound:end purpose -->

**[Configure a contained provider](#configure-the-provider)**.

Without `--model-config`, `sourcebound init` follows the deterministic bootstrap path. Enabling a
provider changes draft selection, not source authority, parsing, or the gate.

## Configure the provider

Save an explicit provider configuration as `.sourcebound/init-provider.yml`. Set `argv[0]` to the
absolute path of an operator-selected command so PATH lookup cannot change the executable. For a
Python provider, `{python}` is the only supported runtime token and is valid only as `argv[0]`; it
resolves to the interpreter running Sourcebound. `env` names only the credentials that command
needs. Do not add `PATH`; Sourcebound supplies a fixed default:

```yaml
adapter: command
name: local-provider
argv: [/absolute/path/to/provider-cli, --json]
timeout_seconds: 300
env: [SOURCEBOUND_PROVIDER_TOKEN]
```

Run init with that configuration:

```bash
sourcebound init --model-config .sourcebound/init-provider.yml
```

## Return bounded selections

The command receives deterministic JSON on standard input and may return only known fact IDs with
allowlisted templates. Its standard output must be one JSON object in this shape:

```json
{
  "drafts": [
    {
      "fact_id": "a fact id copied from the request",
      "template": "provides"
    }
  ]
}
```

The request lists the allowed templates for each fact kind. An empty `drafts` list is valid.
Sourcebound does not pass the repository path, repository working directory, or a write API to the
provider. The command still runs as the caller and can reach absolute host paths or the network when
the host permits it; the [host boundary](SECURITY_MODEL.md#host-boundary) owns that limit.

## Inspect the disclosure receipt

Sourcebound writes `.sourcebound/init-proposer-transcript.json` unless
`--model-transcript` selects another repository-relative path. Absolute paths and paths containing
`..` are rejected. The transcript records the sanitized request, result, and one of three proposer
outcomes: `accept`, `parser-reject`, or `provider-failed`. The separate
`state` is `bootstrap-failed` when the parser accepted the response but repository discovery,
planning, or writing failed afterward. This preserves the parser result while the command exit and
feedback `result_class` record the later failure.

Verify the observed outcome after `init` returns:

```bash
python3 - <<'PY'
import json
from pathlib import Path

receipt = json.loads(
    Path(".sourcebound/init-proposer-transcript.json").read_text(encoding="utf-8")
)
assert receipt["schema"] == "sourcebound.init-proposer-transcript.v1"
assert receipt["state"] == "accepted"
assert receipt["outcome"] == "accept"
assert receipt["model_record"] is not None
print(receipt["outcome"])
PY
```

If that check fails, read `detail` and `state`. `rejected` names a parser refusal,
`provider-failed` names command execution failure, and `bootstrap-failed` names a later repository
failure after an accepted response.

## Failure contract

The parser rejects unknown facts, duplicate selections, unsupported templates, malformed output,
and more than five drafts. A missing, failed, or timed-out provider leaves generated documentation
unwritten. Sourcebound does not block network access; run the selected command in a sandbox when it
must not reach the network.

Return to [evaluation](EVALUATION.md) when the resulting reader task needs a replayable score.
