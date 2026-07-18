from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.execution import PYTHON_EXECUTABLE_TOKEN
from clean_docs.models import (
    Assertion,
    Binding,
    ClaimBinding,
    CommandSpec,
    ContextBundleProjection,
    LlmsTxtProjection,
    Manifest,
    PLUGIN_API_VERSION,
    PLUGIN_INTERFACES,
    PluginSpec,
    ProjectionConfig,
    RegionBinding,
    Source,
    SourceClaimCheck,
    SymbolBinding,
    StaticDemoProjection,
)

ROOT_KEYS = {
    "version",
    "bindings",
    "execution",
    "plugins",
    "projections",
    "source_claim_checks",
}
BINDING_KEYS = {
    "id", "type", "doc", "region", "anchor", "extractor", "source", "renderer",
    "columns", "language", "command", "assertion",
}
SOURCE_KEYS = {"path", "symbol", "pointer", "glob"}
EXTRACTORS = {
    "file", "json", "path", "python-literal", "repository-inventory",
    "repository-overview", "structured-data",
}
RENDERERS = {
    "fenced-text", "markdown-fragment", "markdown-list", "markdown-table", "scalar"
}
EXECUTION_KEYS = {"commands", "allowed_commands"}
COMMAND_KEYS = {"argv", "timeout_seconds", "network"}
ASSERTION_KEYS = {"json_path", "operator", "expected"}
PROJECTION_KEYS = {"llms_txt", "bundles", "demo"}
LLMS_TXT_KEYS = {"output", "title", "summary", "include"}
BUNDLE_KEYS = {"id", "output", "include"}
DEMO_KEYS = {"output", "evidence"}
PLUGIN_KEYS = {"id", "api_version", "interfaces", "argv", "timeout_seconds"}
SOURCE_CLAIM_CHECK_KEYS = {
    "id",
    "kind",
    "doc",
    "anchor",
    "subject",
    "source",
    "locator",
}
SOURCE_CLAIM_KINDS = {"count", "identifier-set"}
MANIFEST_REFERENCE = (
    {
        "binding": "region",
        "required": "id, type, doc, region, extractor, source, renderer",
        "verifies": "Generated content matches source evidence",
    },
    {
        "binding": "claim",
        "required": "id, type, doc, anchor, command, assertion",
        "verifies": "Observed command value matches the assertion",
    },
    {
        "binding": "symbol",
        "required": "id, type, doc, anchor, source",
        "verifies": "A source path or Python symbol still exists",
    },
)


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be a mapping")
    return value


def _reject_unknown(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigurationError(f"{where} has unknown key(s): {', '.join(unknown)}")


def _relative_path(raw: Any, where: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigurationError(f"{where} must be a non-empty path")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{where} must stay inside the repository: {raw}")
    return path


def _one_line(raw: Any, where: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip() or "\n" in raw or "\r" in raw:
        raise ConfigurationError(f"{where} must be one non-empty line")
    return raw.strip()


def _load_projections(raw: Any, bound_docs: set[Path]) -> ProjectionConfig | None:
    if raw is None:
        return None
    data = _mapping(raw, "projections")
    _reject_unknown(data, PROJECTION_KEYS, "projections")
    llms_txt = None
    raw_llms = data.get("llms_txt")
    if raw_llms is not None:
        item = _mapping(raw_llms, "projections.llms_txt")
        _reject_unknown(item, LLMS_TXT_KEYS, "projections.llms_txt")
        raw_include = item.get("include", [])
        if not isinstance(raw_include, list) or not all(
            isinstance(path, str) for path in raw_include
        ):
            raise ConfigurationError("projections.llms_txt.include must be a path list")
        include = tuple(
            _relative_path(path, "projections.llms_txt.include") for path in raw_include
        )
        if len(set(include)) != len(include):
            raise ConfigurationError("projections.llms_txt.include must not contain duplicates")
        llms_txt = LlmsTxtProjection(
            output=_relative_path(item.get("output"), "projections.llms_txt.output"),
            title=_one_line(item.get("title"), "projections.llms_txt.title"),
            summary=_one_line(item.get("summary"), "projections.llms_txt.summary"),
            include=include,
        )
        if llms_txt.output in include:
            raise ConfigurationError(
                "projections.llms_txt.output cannot also be a source document"
            )
    bundles: list[ContextBundleProjection] = []
    raw_bundles = data.get("bundles", [])
    if not isinstance(raw_bundles, list):
        raise ConfigurationError("projections.bundles must be a list")
    bundle_ids: set[str] = set()
    outputs = {llms_txt.output} if llms_txt else set()
    for index, raw_bundle in enumerate(raw_bundles):
        where = f"projections.bundles[{index}]"
        item = _mapping(raw_bundle, where)
        _reject_unknown(item, BUNDLE_KEYS, where)
        bundle_id = item.get("id")
        if not isinstance(bundle_id, str) or not bundle_id.strip():
            raise ConfigurationError(f"{where}.id must be a non-empty string")
        if bundle_id in bundle_ids:
            raise ConfigurationError(f"duplicate context bundle id: {bundle_id}")
        bundle_ids.add(bundle_id)
        output = _relative_path(item.get("output"), f"{where}.output")
        if output in outputs:
            raise ConfigurationError(f"duplicate projection output: {output}")
        outputs.add(output)
        raw_include = item.get("include")
        if (
            not isinstance(raw_include, list)
            or not raw_include
            or not all(isinstance(path, str) for path in raw_include)
        ):
            raise ConfigurationError(f"{where}.include must be a non-empty path list")
        include = tuple(_relative_path(path, f"{where}.include") for path in raw_include)
        if len(set(include)) != len(include):
            raise ConfigurationError(f"{where}.include must not contain duplicates")
        unknown = sorted(path.as_posix() for path in include if path not in bound_docs)
        if unknown:
            raise ConfigurationError(
                f"{where}.include names unbound document(s): {', '.join(unknown)}"
            )
        if output in include:
            raise ConfigurationError(f"{where}.output cannot also be a source document")
        bundles.append(ContextBundleProjection(bundle_id, output, include))
    demo = None
    raw_demo = data.get("demo")
    if raw_demo is not None:
        item = _mapping(raw_demo, "projections.demo")
        _reject_unknown(item, DEMO_KEYS, "projections.demo")
        output = _relative_path(item.get("output"), "projections.demo.output")
        evidence = _relative_path(item.get("evidence"), "projections.demo.evidence")
        if output.suffix.lower() != ".html":
            raise ConfigurationError("projections.demo.output must be an HTML file")
        if output in outputs:
            raise ConfigurationError(f"duplicate projection output: {output}")
        demo = StaticDemoProjection(output, evidence)
    if llms_txt is None and not bundles and demo is None:
        raise ConfigurationError(
            "projections must configure llms_txt, a bundle, or a demo"
        )
    return ProjectionConfig(llms_txt=llms_txt, bundles=tuple(bundles), demo=demo)


def load_manifest(path: Path) -> Manifest:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read manifest {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc

    root = _mapping(raw, "manifest")
    _reject_unknown(root, ROOT_KEYS, "manifest")
    if root.get("version") != 1:
        raise ConfigurationError("manifest version must be 1")
    raw_bindings = root.get("bindings")
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise ConfigurationError("manifest bindings must be a non-empty list")

    plugins: list[PluginSpec] = []
    raw_plugins = root.get("plugins", [])
    if not isinstance(raw_plugins, list):
        raise ConfigurationError("manifest plugins must be a list")
    plugin_ids: set[str] = set()
    for index, raw_plugin in enumerate(raw_plugins):
        where = f"plugins[{index}]"
        plugin_data = _mapping(raw_plugin, where)
        _reject_unknown(plugin_data, PLUGIN_KEYS, where)
        plugin_id = plugin_data.get("id")
        if not isinstance(plugin_id, str) or not plugin_id or not plugin_id.replace("-", "").isalnum():
            raise ConfigurationError(f"{where}.id must contain letters, numbers, and hyphens")
        if plugin_id in plugin_ids:
            raise ConfigurationError(f"duplicate plugin id: {plugin_id}")
        plugin_ids.add(plugin_id)
        api_version = plugin_data.get("api_version")
        if api_version != PLUGIN_API_VERSION:
            raise ConfigurationError(
                f"plugin {plugin_id} API version {api_version} is incompatible; "
                f"clean-docs supports {PLUGIN_API_VERSION}"
            )
        interfaces = plugin_data.get("interfaces")
        if (
            not isinstance(interfaces, list)
            or not interfaces
            or not all(isinstance(item, str) and item in PLUGIN_INTERFACES for item in interfaces)
            or len(set(interfaces)) != len(interfaces)
        ):
            raise ConfigurationError(
                f"{where}.interfaces must be unique values from: "
                + ", ".join(sorted(PLUGIN_INTERFACES))
            )
        argv = plugin_data.get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(item, str) and item for item in argv
        ):
            raise ConfigurationError(f"{where}.argv must be a non-empty string list")
        timeout = plugin_data.get("timeout_seconds", 30)
        if not isinstance(timeout, int) or not 1 <= timeout <= 120:
            raise ConfigurationError(f"{where}.timeout_seconds must be 1..120")
        plugins.append(
            PluginSpec(plugin_id, api_version, tuple(interfaces), tuple(argv), timeout)
        )

    commands: list[CommandSpec] = []
    execution = root.get("execution")
    if execution is not None:
        execution_data = _mapping(execution, "execution")
        _reject_unknown(execution_data, EXECUTION_KEYS, "execution")
        if execution_data.get("commands", "deny") != "deny":
            raise ConfigurationError("execution.commands must be deny")
        allowed = _mapping(execution_data.get("allowed_commands", {}), "execution.allowed_commands")
        for command_id, raw_command in allowed.items():
            command = _mapping(raw_command, f"execution.allowed_commands.{command_id}")
            _reject_unknown(command, COMMAND_KEYS, f"execution.allowed_commands.{command_id}")
            argv = command.get("argv")
            timeout = command.get("timeout_seconds", 30)
            network = command.get("network", False)
            if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
                raise ConfigurationError(f"execution.allowed_commands.{command_id}.argv must be a non-empty string list")
            if PYTHON_EXECUTABLE_TOKEN in argv[1:]:
                raise ConfigurationError(
                    f"execution.allowed_commands.{command_id}.argv may use "
                    f"{PYTHON_EXECUTABLE_TOKEN} only as its executable"
                )
            if not isinstance(timeout, int) or not 1 <= timeout <= 300:
                raise ConfigurationError(f"execution.allowed_commands.{command_id}.timeout_seconds must be 1..300")
            if network is not False:
                raise ConfigurationError(f"execution.allowed_commands.{command_id}.network must be false")
            commands.append(CommandSpec(command_id, tuple(argv), timeout, network))

    source_claim_checks: list[SourceClaimCheck] = []
    raw_source_claim_checks = root.get("source_claim_checks", [])
    if not isinstance(raw_source_claim_checks, list):
        raise ConfigurationError("source_claim_checks must be a list")
    source_claim_ids: set[str] = set()
    for index, raw_check in enumerate(raw_source_claim_checks):
        where = f"source_claim_checks[{index}]"
        check = _mapping(raw_check, where)
        _reject_unknown(check, SOURCE_CLAIM_CHECK_KEYS, where)
        check_id = check.get("id")
        if not isinstance(check_id, str) or not check_id.strip():
            raise ConfigurationError(f"{where}.id must be a non-empty string")
        if check_id in source_claim_ids:
            raise ConfigurationError(f"duplicate source claim check id: {check_id}")
        source_claim_ids.add(check_id)
        kind = check.get("kind")
        if kind not in SOURCE_CLAIM_KINDS:
            raise ConfigurationError(
                f"{where}.kind must be one of: {', '.join(sorted(SOURCE_CLAIM_KINDS))}"
            )
        anchor = check.get("anchor")
        if not isinstance(anchor, str) or not anchor.strip():
            raise ConfigurationError(f"{where}.anchor must be a non-empty string")
        subject = check.get("subject")
        if (
            not isinstance(subject, str)
            or not subject.strip()
            or "\n" in subject
            or "\r" in subject
        ):
            raise ConfigurationError(f"{where}.subject must be one non-empty line")
        locator = check.get("locator")
        if (
            not isinstance(locator, str)
            or not locator.strip()
            or "\n" in locator
            or "\r" in locator
        ):
            raise ConfigurationError(f"{where}.locator must be one non-empty line")
        required_suffix = "#count" if kind == "count" else "#keys"
        if not locator.endswith(required_suffix):
            raise ConfigurationError(
                f"{where}.locator must end with {required_suffix} for {kind}"
            )
        source_claim_checks.append(
            SourceClaimCheck(
                id=check_id,
                kind=kind,
                doc=_relative_path(check.get("doc"), f"{where}.doc"),
                anchor=anchor.strip(),
                subject=subject.strip(),
                source=_relative_path(check.get("source"), f"{where}.source"),
                locator=locator.strip(),
            )
        )

    bindings: list[Binding] = []
    ids: set[str] = set()
    for index, item in enumerate(raw_bindings):
        where = f"bindings[{index}]"
        data = _mapping(item, where)
        _reject_unknown(data, BINDING_KEYS, where)
        binding_id = data.get("id")
        if not isinstance(binding_id, str) or not binding_id.strip():
            raise ConfigurationError(f"{where}.id must be a non-empty string")
        if binding_id in ids:
            raise ConfigurationError(f"duplicate binding id: {binding_id}")
        ids.add(binding_id)
        binding_type = data.get("type")
        if binding_type not in {item["binding"] for item in MANIFEST_REFERENCE}:
            raise ConfigurationError(f"{where}.type must be region, claim, or symbol")
        if binding_type == "claim":
            if data.get("extractor") != "command":
                raise ConfigurationError(f"{where}.extractor must be command for a claim")
            command_ref = data.get("command")
            if not isinstance(command_ref, str) or command_ref not in {item.id for item in commands}:
                raise ConfigurationError(f"{where}.command must name an allowed command")
            assertion_data = _mapping(data.get("assertion"), f"{where}.assertion")
            _reject_unknown(assertion_data, ASSERTION_KEYS, f"{where}.assertion")
            json_path = assertion_data.get("json_path")
            if not isinstance(json_path, str) or not json_path.startswith("$."):
                raise ConfigurationError(f"{where}.assertion.json_path must start with $.")
            if assertion_data.get("operator") != "equals":
                raise ConfigurationError(f"{where}.assertion.operator must be equals")
            anchor = data.get("anchor")
            if not isinstance(anchor, str) or not anchor:
                raise ConfigurationError(f"{where}.anchor must be non-empty")
            bindings.append(ClaimBinding(
                id=binding_id,
                doc=_relative_path(data.get("doc"), f"{where}.doc"),
                anchor=anchor,
                extractor="command",
                command=command_ref,
                assertion=Assertion(json_path, "equals", assertion_data.get("expected")),
            ))
            continue

        source_data = _mapping(data.get("source"), f"{where}.source")
        _reject_unknown(source_data, SOURCE_KEYS, f"{where}.source")
        if binding_type == "symbol":
            symbol = source_data.get("symbol")
            if symbol is not None and (not isinstance(symbol, str) or not symbol.isidentifier()):
                raise ConfigurationError(f"{where}.source.symbol must be a Python identifier")
            anchor = data.get("anchor")
            if not isinstance(anchor, str) or not anchor:
                raise ConfigurationError(f"{where}.anchor must be non-empty")
            bindings.append(SymbolBinding(
                id=binding_id,
                doc=_relative_path(data.get("doc"), f"{where}.doc"),
                anchor=anchor,
                source=Source(
                    path=_relative_path(source_data.get("path"), f"{where}.source.path"),
                    symbol=symbol,
                ),
            ))
            continue

        extractor = data.get("extractor")
        if not isinstance(extractor, str):
            raise ConfigurationError(f"{where}.extractor must be a non-empty string")
        plugin_extractor = (
            extractor.removeprefix("plugin:")
            if extractor.startswith("plugin:")
            else None
        )
        if extractor not in EXTRACTORS and plugin_extractor is None:
            raise ConfigurationError(
                f"{where}.extractor must be one of: {', '.join(sorted(EXTRACTORS))}"
            )
        if plugin_extractor is not None:
            plugin_spec = next(
                (item for item in plugins if item.id == plugin_extractor), None
            )
            if plugin_spec is None or "extractor" not in plugin_spec.interfaces:
                raise ConfigurationError(
                    f"{where}.extractor names plugin {plugin_extractor} without an extractor interface"
                )
        renderer = data.get("renderer")
        if not isinstance(renderer, str):
            raise ConfigurationError(f"{where}.renderer must be a non-empty string")
        plugin_renderer = (
            renderer.removeprefix("plugin:")
            if renderer.startswith("plugin:")
            else None
        )
        if renderer not in RENDERERS and plugin_renderer is None:
            raise ConfigurationError(
                f"{where}.renderer must be one of: {', '.join(sorted(RENDERERS))}"
            )
        if plugin_renderer is not None:
            renderer_spec = next(
                (item for item in plugins if item.id == plugin_renderer), None
            )
            if renderer_spec is None or "renderer" not in renderer_spec.interfaces:
                raise ConfigurationError(
                    f"{where}.renderer names plugin {plugin_renderer} without a renderer interface"
                )

        symbol = source_data.get("symbol")
        pointer = source_data.get("pointer")
        source_glob = source_data.get("glob")
        source_path = source_data.get("path")
        if plugin_extractor is not None:
            if any(value is not None for value in (symbol, pointer, source_glob)):
                raise ConfigurationError(
                    f"{where}.source.path is the only valid plugin extractor source field"
                )
        elif extractor == "python-literal":
            if not isinstance(symbol, str) or not symbol.isidentifier():
                raise ConfigurationError(f"{where}.source.symbol must be a Python identifier")
            if pointer is not None or source_glob is not None:
                raise ConfigurationError(f"{where}.source has fields invalid for python-literal")
        elif extractor == "json":
            if symbol is not None:
                raise ConfigurationError(f"{where}.source.symbol is only valid for python-literal")
            if not isinstance(pointer, str) or not pointer.startswith("/"):
                raise ConfigurationError(
                    f"{where}.source.pointer must be a JSON Pointer starting with /"
                )
        elif extractor == "structured-data":
            if pointer is not None and (
                not isinstance(pointer, str) or not pointer.startswith("/")
            ):
                raise ConfigurationError(f"{where}.source.pointer must start with /")
            if symbol is not None or source_glob is not None:
                raise ConfigurationError(f"{where}.source has fields invalid for structured-data")
        elif extractor == "file":
            if any(value is not None for value in (symbol, pointer, source_glob)):
                raise ConfigurationError(f"{where}.source.path is the only valid file source field")
        elif extractor in {"repository-inventory", "repository-overview"}:
            if source_path != "." or any(
                value is not None for value in (symbol, pointer, source_glob)
            ):
                raise ConfigurationError(
                    f"{where}.source.path must be . for {extractor}"
                )
        else:
            if not isinstance(source_glob, str) or not source_glob:
                raise ConfigurationError(f"{where}.source.glob must be non-empty")
            glob_path = Path(source_glob)
            if glob_path.is_absolute() or ".." in glob_path.parts:
                raise ConfigurationError(f"{where}.source.glob must stay inside the repository")
            if any(value is not None for value in (symbol, pointer, source_path)):
                raise ConfigurationError(f"{where}.source.glob is the only valid path source field")

        compatible = {
            "file": {"fenced-text", "scalar"},
            "json": {"markdown-table"},
            "path": {"markdown-list"},
            "python-literal": {"markdown-fragment", "markdown-table", "scalar"},
            "repository-inventory": {"markdown-table"},
            "repository-overview": {"markdown-fragment"},
            "structured-data": {"markdown-list", "markdown-table", "scalar"},
        }
        if (
            plugin_extractor is None
            and plugin_renderer is None
            and renderer not in compatible[extractor]
        ):
            raise ConfigurationError(
                f"{where}.renderer {renderer} is incompatible with extractor {extractor}"
            )
        language = data.get("language")
        if language is not None and (
            renderer != "fenced-text" or not isinstance(language, str)
        ):
            raise ConfigurationError(f"{where}.language is only valid for fenced-text")
        region = data.get("region")
        if not isinstance(region, str) or not region.strip():
            raise ConfigurationError(f"{where}.region must be a non-empty string")
        columns = data.get("columns", [])
        if renderer == "markdown-table":
            if (
                not isinstance(columns, list)
                or not columns
                or not all(isinstance(column, str) and column for column in columns)
                or len(set(columns)) != len(columns)
            ):
                raise ConfigurationError(f"{where}.columns must be unique non-empty strings")
        elif columns:
            raise ConfigurationError(f"{where}.columns is only valid for markdown-table")
        bindings.append(RegionBinding(
            id=binding_id,
            doc=_relative_path(data.get("doc"), f"{where}.doc"),
            region=region,
            extractor=extractor,
            source=Source(
                path=Path(".") if extractor == "path" else _relative_path(
                    source_path, f"{where}.source.path"
                ),
                symbol=symbol,
                pointer=pointer,
                glob=source_glob,
            ),
            renderer=renderer,
            columns=tuple(columns),
            language=language,
        ))
    projections = _load_projections(
        root.get("projections"), {binding.doc for binding in bindings}
    )
    return Manifest(
        path=path,
        version=1,
        bindings=tuple(bindings),
        commands=tuple(commands),
        plugins=tuple(plugins),
        projections=projections,
        source_claim_checks=tuple(source_claim_checks),
    )
