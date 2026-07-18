# Extension API

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this reference when first-party adapters cannot cover a repository surface and you need an external extractor, discoverer, renderer, or policy check. It gives plugin authors the versioned process protocol and isolation boundary required to add evidence without taking control of facts or coverage.
<!-- clean-docs:end purpose -->

## Declare a plugin

Plugins use API version `1` and name every interface they implement. Declare the command as an argument array:

```yaml
version: 1
plugins:
  - id: ecosystem
    api_version: 1
    interfaces: [extractor, discoverer]
    argv: ["{python}", tools/ecosystem_plugin.py]
    timeout_seconds: 30
```

An incompatible API version exits `2` before clean-docs invokes the command. `{python}` selects the interpreter running clean-docs; literal executables keep normal process lookup.

## Implement the process protocol

clean-docs writes one JSON request to standard input. The request uses `clean-docs.plugin-request.v1` and carries `api_version`, `operation`, immutable snapshot ref, and operation payload. The command returns one JSON object using `clean-docs.plugin-response.v1`, API version `1`, and a `result` object.

| Interface | Input | Required result |
| --- | --- | --- |
| `extractor` | Binding, source, renderer, and columns | `kind` and normalized `value` |
| `discoverer` | Snapshot working directory | `items` with kind, name, source, locator, and evidence |
| `renderer` | Binding plus normalized evidence | Text `content` |
| `policy` | Planned document map | Typed `findings` with doc, line, rule, and detail |

Core code computes evidence digests, validates repository-relative source paths, and attaches `plugin:<id>` provenance. Duplicate inventory IDs fail instead of replacing first-party or plugin evidence. A plugin cannot set its own coverage state or rewrite deterministic facts.

## Isolation boundary

Each invocation runs in a disposable repository copy with a temporary home and temporary directory. Writes in that copy are discarded, symbolic links are rejected, output is capped at 1 MB, and the configured timeout stops hanging commands. clean-docs passes no credentials through the environment.

The execution environment still owns network isolation and operating-system sandboxing. Run untrusted plugins inside a network-blocked container or CI runner; the local process contract does not claim to be an OS security boundary.

## Bind plugin evidence

Name an extractor or renderer as `plugin:<id>`:

```yaml
bindings:
  - id: ecosystem-commands
    type: region
    doc: docs/COMMANDS.md
    region: commands
    extractor: plugin:ecosystem
    source: {path: ecosystem.config}
    renderer: markdown-list
```

Plugin extractors participate in `derive`, `drive`, and `check`. Discoverers participate in inventory, changed-surface checks, and release deltas. Policy plugins run against the planned document bytes before writes.

## Migrate a prior manifest

Preview a version `0` to version `1` migration before writing:

```bash
clean-docs migrate
clean-docs migrate --write
```

The write creates `.clean-docs.yml.v0.bak` before replacing the manifest. Restore the exact prior bytes with:

```bash
clean-docs migrate --rollback
```

Migration changes schema syntax only. Golden tests require the migrated manifest to produce the same normalized evidence and rendered documentation.
