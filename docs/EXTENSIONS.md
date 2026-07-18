# Extension API

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Plugin authors come here when first-party adapters cannot represent a repository surface. The
versioned process protocol adds extractors, discoverers, renderers, or policy findings without
letting the plugin seize factual authority or coverage state.
<!-- clean-docs:end purpose -->

**[Declare the plugin process](#declare-a-plugin)**.

An incompatible API exits `2` before execution; the final `clean-docs check` result proves that
accepted plugin evidence still satisfies its binding.

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

clean-docs writes one JSON request to standard input. The request uses
`clean-docs.plugin-request.v1`. It carries `api_version`, `operation`, an immutable snapshot ref, and
the task payload. The command returns one `clean-docs.plugin-response.v1` JSON object with API
version `1` and a `result` object.

| Interface | Input | Required result |
| --- | --- | --- |
| `extractor` | Binding, source, renderer, and columns | `kind` and normalized `value` |
| `discoverer` | Snapshot working directory | `items` with kind, name, source, locator, and evidence |
| `renderer` | Binding plus normalized evidence | Text `content` |
| `policy` | Planned document map | Typed `findings` with doc, line, rule, and detail |

Core code computes evidence digests, validates repository-relative source paths, and attaches `plugin:<id>` provenance. Duplicate inventory IDs fail instead of replacing first-party or plugin evidence. A plugin cannot set its own coverage state or rewrite deterministic facts.

## Isolation boundary

Each invocation runs in a disposable repository copy with a temporary home and temporary directory. Writes in that copy are discarded, symbolic links are rejected, output is capped at 1 MB, and the configured timeout stops hanging commands. clean-docs passes no credentials through the environment.

The host still decides whether a plugin can reach the network or host filesystem. Run untrusted
plugins inside a network-blocked container or CI runner; the local process contract does not claim
to be an OS security boundary.

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

Preview the update from a version `0` manifest to version `1` before writing:

```bash
clean-docs migrate
clean-docs migrate --write
```

The write creates `.clean-docs.yml.v0.bak` before replacing the manifest. Restore the exact prior bytes with:

```bash
clean-docs migrate --rollback
```

Migration changes schema syntax only. Golden tests require the migrated manifest to produce the same normalized evidence and rendered documentation.
