# Install and manage Sourcebound

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Operators come here to install a released Sourcebound wheel, keep dependencies offline when needed,
or move between versions without changing repository documentation. Each path ends with a local
version or artifact check, so the executable is known before it becomes a gate.
<!-- sourcebound:end purpose -->

**[Install the latest stable release](#install-the-latest-stable-release)**.

## Install with a Python tool installer

After a stable Sourcebound release reaches PyPI, install the CLI in an isolated environment:

```bash
uv tool install sourcebound
sourcebound --version
```

Use `pipx install sourcebound` for the same persistent command, or `uvx sourcebound --help` once.
PyPI receives the same attested wheel published as a GitHub Release asset.

## Install the latest stable release

From the repository you want to protect, download the latest stable wheel and let `pip` resolve
PyYAML from your configured package index:

```bash
release_dir="$(mktemp -d)"
gh release download --repo owieschon/sourcebound \
  --pattern 'sourcebound-*-py3-none-any.whl' --dir "$release_dir"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "$release_dir"/sourcebound-*.whl
sourcebound --version
```

The version must match the wheel filename. A GitHub release contains the Sourcebound wheel, its SPDX
file, checksums, and attestations. It does not contain dependency wheels.

The supported executable is `sourcebound`. Install the current wheel when moving from an earlier
package identity; do not preserve an unverified local alias as a CI contract.

## Install without package-index access

Place the Sourcebound wheel and a compatible PyYAML wheel in a local `wheelhouse`, then prohibit index
access:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --no-index --find-links ./wheelhouse ./wheelhouse/sourcebound-*.whl
sourcebound --version
```

The install fails when the wheelhouse cannot satisfy a declared dependency. It does not fall back to
a package index.

## Parse MDX repositories

Python-only repositories do not need Node.js. A repository with tracked `.mdx` documents needs
Node.js 20 or newer for the bundled structural parser:

```bash
node --version
sourcebound doctor
```

`doctor` reports `mdx-parser` as ready when the runtime and bundled parser are present. Without
that runtime, Markdown remains available while every MDX document stays explicitly unsupported.
Sourcebound never downloads Node.js or parser packages during an audit.

The [runtime architecture](ARCHITECTURE.md) explains why MDX uses this bounded adapter rather than
making Node.js a requirement for every Sourcebound installation.

## Upgrade, roll back, or remove the executable

Install the newer wheel, then preview any requested manifest change before writing:

```bash
python -m pip install --upgrade ./sourcebound-*.whl
sourcebound migrate
sourcebound migrate --write
```

`migrate --write` stores the prior manifest bytes in `.sourcebound.yml.v0.bak`. Restore them with
`sourcebound migrate --rollback`. Reinstall the prior wheel to roll back the executable.

Remove the package with:

```bash
python -m pip uninstall sourcebound
```

Uninstalling leaves repository manifests and documentation in place.

## Verify release artifacts

Download the wheel and its checksum file into one directory:

```bash
artifact_dir="$(mktemp -d)"
gh release download --repo owieschon/sourcebound \
  --pattern 'sourcebound-*-py3-none-any.whl' \
  --pattern SHA256SUMS \
  --dir "$artifact_dir"
cd "$artifact_dir"
```

### Check the wheel bytes

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

### Verify the attestation

Ask GitHub to match the wheel to its build provenance:

```bash
gh attestation verify ./sourcebound-*.whl \
  --repo owieschon/sourcebound
```

The checksum step is local. The attestation command needs GitHub access, so run it outside a
network-blocked environment. The release gate also exercises upgrade, executable rollback, a second
upgrade, and uninstall.

Return to the [support guide](SUPPORT.md) to adopt an existing corpus, pin the reusable CI gate, or
build a diagnostic bundle.
