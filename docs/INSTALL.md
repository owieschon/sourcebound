# Install and manage clean-docs

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Operators come here to install a released clean-docs wheel, keep dependencies offline when needed,
or move between versions without changing repository documentation. Each path ends with a local
version or artifact check, so the executable is known before it becomes a gate.
<!-- clean-docs:end purpose -->

**[Install the latest stable release](#install-the-latest-stable-release)**.

The reported version is the first proof; release checks add the wheel digest and attestation.

## Install the latest stable release

From the repository you want to protect, download the latest stable wheel and let `pip` resolve
PyYAML from your configured package index:

```bash
release_dir="$(mktemp -d)"
gh release download --repo owieschon/clean-docs \
  --pattern 'clean_docs-*-py3-none-any.whl' --dir "$release_dir"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "$release_dir"/clean_docs-*.whl
clean-docs --version
```

The version must match the wheel filename. A GitHub release contains the clean-docs wheel, its SPDX
file, checksums, and attestations. It does not contain dependency wheels.

## Install without package-index access

Place the clean-docs wheel and a compatible PyYAML wheel in a local `wheelhouse`, then prohibit index
access:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --no-index --find-links ./wheelhouse ./wheelhouse/clean_docs-*.whl
clean-docs --version
```

The install fails when the wheelhouse cannot satisfy a declared dependency. It does not fall back to
a package index.

## Parse MDX repositories

Python-only repositories do not need Node.js. A repository with tracked `.mdx` documents needs
Node.js 20 or newer for the bundled structural parser:

```bash
node --version
clean-docs doctor
```

`doctor` reports `mdx-parser` as ready when the runtime and bundled parser are present. Without
that runtime, Markdown remains available while every MDX document stays explicitly unsupported.
clean-docs never downloads Node.js or parser packages during an audit.

## Upgrade, roll back, or remove the executable

Install the newer wheel, then preview any requested manifest change before writing:

```bash
python -m pip install --upgrade ./clean_docs-*.whl
clean-docs migrate
clean-docs migrate --write
```

`migrate --write` stores the prior manifest bytes in `.clean-docs.yml.v0.bak`. Restore them with
`clean-docs migrate --rollback`. Reinstall the prior wheel to roll back the executable.

Remove the package with:

```bash
python -m pip uninstall clean-docs
```

Uninstalling leaves repository manifests and documentation in place.

## Verify release artifacts

Download the wheel and its checksum file into one directory:

```bash
artifact_dir="$(mktemp -d)"
gh release download --repo owieschon/clean-docs \
  --pattern 'clean_docs-*-py3-none-any.whl' \
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

wheels = list(Path(".").glob("clean_docs-*.whl"))
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
gh attestation verify ./clean_docs-*.whl \
  --repo owieschon/clean-docs
```

The checksum step is local. The attestation command needs GitHub access, so run it outside a
network-blocked environment. The release gate also exercises upgrade, executable rollback, a second
upgrade, and uninstall.

Return to the [support guide](SUPPORT.md) to adopt an existing corpus, pin the reusable CI gate, or
build a diagnostic bundle.
