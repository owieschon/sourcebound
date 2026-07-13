from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from clean_docs.errors import ConfigurationError

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


SKIP_PARTS = {".git", ".venv", "build", "dist", "node_modules", "__pycache__"}
SKIP_PATHS = {".clean-docs.yml", ".clean-docs-residue.yml", "llms.txt"}
LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
}
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
TS_EXPORT = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:abstract\s+)?"
    r"(?:function|class|const|interface|type|enum)\s+([A-Za-z_$][\w$]*)",
    re.M,
)
TS_CLI_COMMAND = re.compile(r"\.command\(\s*['\"]([^'\"]+)['\"]")
TS_CLI_OPTION = re.compile(r"\.option\(\s*['\"]([^'\"]+)['\"]")
TS_MCP_TOOL = re.compile(r"\.tool\(\s*['\"]([^'\"]+)['\"]")
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
PYTHON_TOOLING_MODULES = {"conftest.py", "noxfile.py", "setup.py"}


@dataclass(frozen=True)
class InventoryItem:
    id: str
    kind: str
    name: str
    source: str
    locator: str
    adapter: str
    digest: str
    coverage: str
    coverage_reason: str | None = None


@dataclass(frozen=True)
class InventoryReport:
    languages: tuple[str, ...]
    items: tuple[InventoryItem, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "clean-docs.inventory.v1",
            "languages": list(self.languages),
            "items": [asdict(item) for item in self.items],
            "counts": {
                state: sum(item.coverage == state for item in self.items)
                for state in ("bound", "ignored", "standard-gap")
            },
        }


def _repository_files(root: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        candidates = [root / item for item in proc.stdout.decode().split("\0") if item]
    else:
        candidates = list(root.rglob("*"))
    return sorted(
        path
        for path in candidates
        if path.is_file()
        and not set(path.relative_to(root).parts) & SKIP_PARTS
        and "docs/archive" not in path.relative_to(root).as_posix()
        and path.relative_to(root).as_posix() not in SKIP_PATHS
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _identifier(kind: str, source: str, locator: str) -> str:
    return f"{kind}:{source}:{locator}"


def _item(
    kind: str,
    name: str,
    source: str,
    locator: str,
    adapter: str,
    evidence: str,
) -> dict[str, str]:
    return {
        "id": _identifier(kind, source, locator),
        "kind": kind,
        "name": name,
        "source": source,
        "locator": locator,
        "adapter": adapter,
        "digest": _digest(evidence),
    }


def _python_evidence(text: str, node: ast.AST) -> str:
    """Return source-bound evidence that is stable across CPython AST versions."""
    parts = []
    decorators = getattr(node, "decorator_list", ())
    for decorator in decorators:
        segment = ast.get_source_segment(text, decorator)
        if segment is not None:
            parts.append(segment)
    segment = ast.get_source_segment(text, node)
    if segment is not None:
        parts.append(segment)
    return "\n".join(parts)


def _python_items(path: str, text: str) -> list[dict[str, str]]:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError:
        return []
    items: list[dict[str, str]] = []
    is_test = Path(path).name.startswith("test_") or "/tests/" in f"/{path}"
    if not is_test and Path(path).name not in PYTHON_TOOLING_MODULES:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                items.append(_item("api-symbol", node.name, path, node.name, "python-ast", _python_evidence(text, node)))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [ast.unparse(item).lower() for item in node.decorator_list]
                if any("tool" in item for item in decorators):
                    items.append(_item("mcp-tool", node.name, path, node.name, "python-ast", _python_evidence(text, node)))
                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call) or not isinstance(
                        decorator.func, ast.Attribute
                    ):
                        continue
                    if decorator.func.attr != "command":
                        continue
                    command_name = node.name
                    if (
                        decorator.args
                        and isinstance(decorator.args[0], ast.Constant)
                        and isinstance(decorator.args[0].value, str)
                    ):
                        command_name = decorator.args[0].value
                    items.append(
                        _item(
                            "cli-command",
                            command_name,
                            path,
                            command_name,
                            "python-cli-framework",
                            _python_evidence(text, node),
                        )
                    )
            if isinstance(node, ast.ClassDef) and any(
                "basesettings" in ast.unparse(base).lower() for base in node.bases
            ):
                for field in node.body:
                    if isinstance(field, (ast.Assign, ast.AnnAssign)):
                        target = field.target if isinstance(field, ast.AnnAssign) else field.targets[0]
                        if isinstance(target, ast.Name) and not target.id.startswith("_"):
                            items.append(
                                _item(
                                    "config-key",
                                    target.id,
                                    path,
                                    f"{node.name}.{target.id}",
                                    "python-settings-ast",
                                    _python_evidence(text, field),
                                )
                            )
    for candidate in ast.walk(tree):
        if not isinstance(candidate, ast.Call) or not isinstance(candidate.func, ast.Attribute):
            continue
        if not candidate.args or not isinstance(candidate.args[0], ast.Constant) or not isinstance(candidate.args[0].value, str):
            continue
        value = candidate.args[0].value
        if candidate.func.attr == "add_parser":
            items.append(_item("cli-command", value, path, value, "argparse-ast", _python_evidence(text, candidate)))
        elif candidate.func.attr == "add_argument" and value.startswith("-"):
            items.append(_item("cli-option", value, path, value, "argparse-ast", _python_evidence(text, candidate)))
    return items


def _structured(path: Path, text: str) -> Any:
    try:
        if path.suffix.lower() == ".json":
            return json.loads(text)
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(text)
        if path.name == "pyproject.toml":
            return tomllib.loads(text)
    except (json.JSONDecodeError, yaml.YAMLError, tomllib.TOMLDecodeError):
        return None
    return None


def _structured_items(path: str, data: Any) -> list[dict[str, str]]:
    if not isinstance(data, dict):
        return []
    items: list[dict[str, str]] = []
    if path == "pyproject.toml" and isinstance(data.get("project"), dict):
        project = data["project"]
        name = str(project.get("name", "Python package"))
        version = str(project.get("version", "unknown"))
        items.append(_item("package", name, path, "project", "python-package", f"{name}:{version}"))
    if path == "package.json":
        name = str(data.get("name", "JavaScript package"))
        version = str(data.get("version", "unknown"))
        items.append(_item("package", name, path, "package", "node-package", f"{name}:{version}"))
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            for script, command in sorted(scripts.items()):
                if str(script).startswith("//"):
                    continue
                kind = "test-runner" if script == "test" or script.startswith("test:") else "package-script"
                items.append(_item(kind, str(script), path, f"scripts.{script}", "node-package", str(command)))
        binaries = data.get("bin")
        if isinstance(binaries, str):
            items.append(_item("cli-command", name, path, "bin", "node-package", binaries))
        elif isinstance(binaries, dict):
            for command, target in sorted(binaries.items()):
                items.append(_item("cli-command", str(command), path, f"bin.{command}", "node-package", str(target)))
    if "openapi" in data and isinstance(data.get("paths"), dict):
        for route, operations in sorted(data["paths"].items()):
            if not isinstance(operations, dict):
                continue
            for method in sorted(set(operations) & HTTP_METHODS):
                locator = f"{method.upper()} {route}"
                items.append(_item("api-endpoint", locator, path, locator, "openapi", json.dumps(operations[method], sort_keys=True)))
    if "$schema" in data or path.endswith(".schema.json"):
        name = str(data.get("title") or data.get("$id") or Path(path).stem)
        items.append(_item("schema", name, path, name, "json-schema", json.dumps(data, sort_keys=True)))
        properties = data.get("properties")
        if isinstance(properties, dict):
            for key, value in sorted(properties.items()):
                items.append(
                    _item(
                        "config-key",
                        str(key),
                        path,
                        f"properties.{key}",
                        "json-schema",
                        json.dumps(value, sort_keys=True),
                    )
                )
    return items


def _coverage_ignores(root: Path, identifiers: set[str]) -> dict[str, str]:
    ignore_path = root / ".clean-docs-ignore.yml"
    if not ignore_path.exists():
        return {}
    try:
        raw = yaml.safe_load(ignore_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read coverage policy {ignore_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid coverage policy {ignore_path}") from exc
    if not isinstance(raw, dict) or set(raw) != {"version", "ignore"}:
        raise ConfigurationError("coverage policy must contain only version and ignore")
    if raw["version"] != 1 or not isinstance(raw["ignore"], list):
        raise ConfigurationError("coverage policy must use version 1 and an ignore list")
    ignored: dict[str, str] = {}
    for index, record in enumerate(raw["ignore"]):
        if not isinstance(record, dict) or set(record) != {"id", "reason"}:
            raise ConfigurationError(f"coverage ignore {index} must contain id and reason")
        identifier = record["id"]
        reason = record["reason"]
        if not isinstance(identifier, str) or identifier not in identifiers:
            raise ConfigurationError(f"coverage ignore {index} names an unknown inventory id")
        if not isinstance(reason, str) or len(reason.strip()) < 12:
            raise ConfigurationError(f"coverage ignore {index} needs a specific reason")
        if identifier in ignored:
            raise ConfigurationError(f"coverage ignore {index} duplicates an inventory id")
        ignored[identifier] = reason.strip()
    return ignored


def _coverage(root: Path, identifiers: set[str]) -> tuple[bool, dict[str, str]]:
    bound = False
    manifest = root / ".clean-docs.yml"
    if manifest.exists():
        try:
            manifest_text = manifest.read_text(encoding="utf-8")
            bound = any(
                f"extractor: {extractor}" in manifest_text
                for extractor in ("repository-inventory", "repository-overview")
            )
        except OSError:
            pass
    return bound, _coverage_ignores(root, identifiers)


def scan_inventory(root: Path) -> InventoryReport:
    root = root.resolve()
    raw_items: list[dict[str, str]] = []
    languages: set[str] = set()
    for file_path in _repository_files(root):
        relative = file_path.relative_to(root).as_posix()
        language = LANGUAGES.get(file_path.suffix.lower())
        if language:
            languages.add(language)
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if file_path.suffix.lower() == ".py":
            raw_items.extend(_python_items(relative, text))
        if file_path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}:
            adapter = (
                "typescript-static"
                if file_path.suffix.lower() in {".ts", ".tsx"}
                else "javascript-static"
            )
            for name in TS_EXPORT.findall(text):
                raw_items.append(_item("api-symbol", name, relative, name, adapter, name))
            for name in TS_CLI_COMMAND.findall(text):
                raw_items.append(
                    _item("cli-command", name, relative, name, "typescript-cli-framework", name)
                )
            for name in TS_CLI_OPTION.findall(text):
                raw_items.append(
                    _item("cli-option", name, relative, name, "typescript-cli-framework", name)
                )
            for name in TS_MCP_TOOL.findall(text):
                raw_items.append(_item("mcp-tool", name, relative, name, "typescript-mcp", name))
        data = _structured(file_path, text)
        if data is not None:
            raw_items.extend(_structured_items(relative, data))
        if file_path.suffix.lower() == ".md":
            raw_items.append(_item("document", relative, relative, "document", "markdown", text))
            for line_number, line in enumerate(text.splitlines(), start=1):
                for target in LINK.findall(line):
                    raw_items.append(_item("doc-link", target, relative, f"line {line_number}", "markdown-links", target))
        if (
            file_path.name.startswith("test_") and file_path.suffix == ".py"
        ) or file_path.name.endswith((".test.ts", ".spec.ts", ".test.js", ".spec.js")):
            raw_items.append(_item("test-suite", relative, relative, "file", "test-files", text))
    declaration_symbols = {
        (item["name"], item["source"][:-5])
        for item in raw_items
        if item["kind"] == "api-symbol" and item["source"].endswith(".d.ts")
    }
    raw_items = [
        item
        for item in raw_items
        if not (
            item["kind"] == "api-symbol"
            and not item["source"].endswith(".d.ts")
            and (item["name"], str(Path(item["source"]).with_suffix("")))
            in declaration_symbols
        )
    ]
    unique = {item["id"]: item for item in raw_items}
    bound, ignored = _coverage(root, set(unique))
    items = []
    for identifier in sorted(unique):
        item = unique[identifier]
        coverage = "ignored" if identifier in ignored else "bound" if bound else "standard-gap"
        items.append(
            InventoryItem(
                **item,
                coverage=coverage,
                coverage_reason=ignored.get(identifier),
            )
        )
    return InventoryReport(tuple(sorted(languages)), tuple(items))
