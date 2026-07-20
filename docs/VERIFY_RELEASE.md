# Verify a Sourcebound release

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Operators use this guide to confirm that a published Sourcebound wheel matches its checksum and
GitHub attestation before they trust it as a local or CI gate.
<!-- sourcebound:end purpose -->

**[Download the published artifacts](#download-the-published-artifacts)**.

## Download the published artifacts

Download the wheel and its checksum file into one directory:

```bash
artifact_dir="$(mktemp -d)"
gh release download --repo owieschon/sourcebound \
  --pattern 'sourcebound-*-py3-none-any.whl' \
  --pattern SHA256SUMS \
  --dir "$artifact_dir"
cd "$artifact_dir"
```

## Check the wheel bytes

Verify the one wheel without requiring every release asset to be present:

```bash
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path

wheels = list(Path(".").glob("sourcebound-*.whl"))
if len(wheels) != 1:
    raise SystemExit(f"expected one wheel, found {len(wheels)}")
expected = {
    filename: digest
    for digest, filename in (
        line.split(maxsplit=1) for line in Path("SHA256SUMS").read_text().splitlines()
    )
}
actual = sha256(wheels[0].read_bytes()).hexdigest()
if expected.get(wheels[0].name) != actual:
    raise SystemExit("wheel checksum mismatch")
print(f"{wheels[0].name}: {actual}")
PY
```

The printed digest must match the wheel entry in `SHA256SUMS`.

## Verify the attestation

Ask GitHub to match the wheel to its build provenance:

```bash
gh attestation verify ./sourcebound-*.whl \
  --repo owieschon/sourcebound
```

The checksum step is local. The attestation command needs GitHub access, so run it outside a
network-blocked environment. Each release workflow also compares the GitHub and PyPI wheel bytes,
then installs that exact version with both `pipx` and `uv`.

When publication reaches PyPI, the workflow uploads a
`sourcebound.publication-verification.v1` receipt with `ok: true` or the observed failure. The
receipt records the local checksum, wheel digests observed from GitHub and PyPI, attestation status,
and both installed versions on success.

Return to the [installation guide](INSTALL.md) to install, upgrade, roll back, or remove the
executable.
