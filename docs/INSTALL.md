# Install and manage Sourcebound

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Operators come here to install a released Sourcebound wheel, keep dependencies offline when needed,
or move between versions without changing repository documentation. Each path ends with a local
version or artifact check, so the executable is known before it becomes a gate.
<!-- sourcebound:end purpose -->

**[Install Sourcebound with pipx](#install-with-a-python-tool-installer)**.

## Install with a Python tool installer

Install the stable Sourcebound CLI from PyPI in an isolated environment:

```bash
pipx install sourcebound
sourcebound --version
```

Use `uv tool install sourcebound` for the same persistent command, or `uvx sourcebound --help` for
one invocation. The release workflow publishes the same attested wheel to PyPI and GitHub.

## Install from a GitHub release

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

Use the same tool that installed Sourcebound. Upgrade the executable, confirm its version, then
preview any requested manifest change before writing:

```bash
pipx upgrade sourcebound
sourcebound migrate
sourcebound migrate --write
```

With `uv`, replace the first command with `uv tool upgrade sourcebound`.

`migrate --write` stores the prior manifest bytes in `.sourcebound.yml.v0.bak`. Restore them with
`sourcebound migrate --rollback`. Reinstall an exact prior version to roll back the executable:

```bash
pipx install --force "sourcebound==<version>"
```

With `uv`, run `uv tool install --force "sourcebound==<version>"` instead. If you installed a local
wheel in a virtual environment, replace it with:

```bash
python -m pip install --upgrade ./sourcebound-*.whl
```

Remove the tool with the installer that owns it:

```bash
pipx uninstall sourcebound
```

With `uv`, run `uv tool uninstall sourcebound`.

Uninstalling leaves repository manifests and documentation in place.

Use the [release verification guide](VERIFY_RELEASE.md) when you need to check published wheel bytes
or provenance. Return to the [support guide](SUPPORT.md) to adopt an existing corpus, pin the
reusable CI gate, or build a diagnostic bundle.
