from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any


MDX_PARSE_SCHEMA = "clean-docs.mdx-parse.v1"
MDX_PARSE_BATCH_SCHEMA = "clean-docs.mdx-parse-batch.v1"
MDX_PARSE_REQUEST_SCHEMA = "clean-docs.mdx-parse-request.v1"
MDX_PARSER_ID = "@mdx-js/mdx@3.1.1"
MDX_CONTROL = re.compile(
    r"^(?P<indent>\s*)\{/\*\s*(?P<body>clean-docs:.*?)\s*\*/\}\s*$"
)


class MdxParserError(RuntimeError):
    """The first-party MDX parser could not establish a structural result."""


@dataclass(frozen=True)
class MdxLink:
    line: int
    column: int
    url: str


@dataclass(frozen=True)
class MdxNode:
    type: str
    start_line: int
    start_column: int
    start_byte: int
    end_line: int
    end_column: int
    end_byte: int
    name: str | None = None
    url: str | None = None
    depth: int | None = None
    text: str | None = None
    language: str | None = None
    meta: str | None = None
    alt: str | None = None


@dataclass(frozen=True)
class MdxDocument:
    digest: str
    masked_text: str
    links: tuple[MdxLink, ...]
    nodes: tuple[MdxNode, ...]
    parser: str = MDX_PARSER_ID

    def policy_text(self, source: str) -> str:
        source_lines = source.splitlines(keepends=True)
        masked_lines = self.masked_text.splitlines(keepends=True)
        if len(source_lines) != len(masked_lines):
            raise MdxParserError("MDX parser changed the document line structure")
        for index, line in enumerate(source_lines):
            content = line.rstrip("\r\n")
            ending = line[len(content):]
            match = MDX_CONTROL.match(content)
            if match:
                masked_lines[index] = (
                    f"{match.group('indent')}<!-- {match.group('body').strip()} -->"
                    f"{ending}"
                )
        return "".join(masked_lines)


def parser_path() -> Path:
    return Path(str(files("clean_docs.adapters").joinpath("mdx_parser.mjs")))


def parser_availability() -> tuple[bool, str]:
    node = shutil.which("node")
    if node is None:
        return False, "Node.js executable not found"
    try:
        version_process = subprocess.run(
            [node, "--version"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"cannot inspect Node.js runtime: {exc}"
    match = re.fullmatch(r"v(\d+)\.\d+\.\d+\s*", version_process.stdout)
    if version_process.returncode != 0 or match is None:
        return False, "Node.js runtime did not report a semantic version"
    if int(match.group(1)) < 20:
        return False, f"Node.js 20 or newer is required; found {version_process.stdout.strip()}"
    bundled = parser_path()
    if not bundled.is_file():
        return False, "bundled MDX parser not found"
    return True, f"{MDX_PARSER_ID} via {node}"


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise MdxParserError(f"MDX parser returned invalid {field}")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise MdxParserError(f"MDX parser returned invalid {field}")
    return value


def _node(raw: Any) -> MdxNode:
    if not isinstance(raw, dict):
        raise MdxParserError("MDX parser returned an invalid node")
    start = raw.get("start")
    end = raw.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        raise MdxParserError("MDX parser returned a node without positions")
    name = raw.get("name")
    url = raw.get("url")
    text = raw.get("text")
    language = raw.get("language")
    meta = raw.get("meta")
    alt = raw.get("alt")
    depth = raw.get("depth")
    if name is not None and not isinstance(name, str):
        raise MdxParserError("MDX parser returned an invalid node name")
    if url is not None and not isinstance(url, str):
        raise MdxParserError("MDX parser returned an invalid node URL")
    if text is not None and not isinstance(text, str):
        raise MdxParserError("MDX parser returned invalid heading text")
    if language is not None and not isinstance(language, str):
        raise MdxParserError("MDX parser returned invalid code language")
    if meta is not None and not isinstance(meta, str):
        raise MdxParserError("MDX parser returned invalid code metadata")
    if alt is not None and not isinstance(alt, str):
        raise MdxParserError("MDX parser returned invalid image alternative text")
    if depth is not None:
        depth = _integer(depth, "heading depth", minimum=1)
    return MdxNode(
        type=_string(raw.get("type"), "node type"),
        start_line=_integer(start.get("line"), "start line", minimum=1),
        start_column=_integer(start.get("column"), "start column", minimum=1),
        start_byte=_integer(start.get("byte"), "start byte"),
        end_line=_integer(end.get("line"), "end line", minimum=1),
        end_column=_integer(end.get("column"), "end column", minimum=1),
        end_byte=_integer(end.get("byte"), "end byte"),
        name=name,
        url=url,
        depth=depth,
        text=text,
        language=language,
        meta=meta,
        alt=alt,
    )


def _parse_payload(payload: Any, text: str) -> MdxDocument:
    if not isinstance(payload, dict) or payload.get("schema") != MDX_PARSE_SCHEMA:
        raise MdxParserError("MDX parser returned an unsupported document schema")
    if payload.get("parser") != MDX_PARSER_ID:
        raise MdxParserError("MDX parser identity does not match the packaged adapter")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if payload.get("digest") != digest:
        raise MdxParserError("MDX parser input digest does not match")
    masked = _string(payload.get("masked"), "masked document")
    if masked.count("\n") != text.count("\n"):
        raise MdxParserError("MDX parser changed the document line structure")
    raw_links = payload.get("links")
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_links, list) or not isinstance(raw_nodes, list):
        raise MdxParserError("MDX parser omitted semantic results")
    links: list[MdxLink] = []
    for raw in raw_links:
        if not isinstance(raw, dict):
            raise MdxParserError("MDX parser returned an invalid link")
        links.append(
            MdxLink(
                line=_integer(raw.get("line"), "link line", minimum=1),
                column=_integer(raw.get("column"), "link column", minimum=1),
                url=_string(raw.get("url"), "link URL"),
            )
        )
    return MdxDocument(
        digest=digest,
        masked_text=masked,
        links=tuple(links),
        nodes=tuple(_node(raw) for raw in raw_nodes),
    )


def parse_mdx_documents(
    documents: Mapping[str, str],
) -> tuple[dict[str, MdxDocument], dict[str, str]]:
    available, detail = parser_availability()
    if not available:
        raise MdxParserError(detail)
    environment = {
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", ""),
        "TZ": "UTC",
    }
    with tempfile.TemporaryDirectory(prefix="clean-docs-mdx-") as working:
        try:
            process = subprocess.run(
                ["node", "--no-warnings", str(parser_path())],
                input=json.dumps(
                    {
                        "schema": MDX_PARSE_REQUEST_SCHEMA,
                        "documents": [
                            {"id": identifier, "text": text}
                            for identifier, text in sorted(documents.items())
                        ],
                    },
                    separators=(",", ":"),
                ),
                text=True,
                capture_output=True,
                cwd=working,
                env=environment,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise MdxParserError(f"MDX parser failed: {exc}") from exc
    if process.returncode != 0:
        detail = process.stderr.strip() or "parser exited without a diagnostic"
        raise MdxParserError(f"MDX parser failed: {detail}")
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise MdxParserError("MDX parser returned invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema") != MDX_PARSE_BATCH_SCHEMA:
        raise MdxParserError("MDX parser returned an unsupported batch schema")
    raw_results = payload.get("documents")
    if not isinstance(raw_results, list):
        raise MdxParserError("MDX parser omitted batch results")
    parsed: dict[str, MdxDocument] = {}
    errors: dict[str, str] = {}
    for raw in raw_results:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            raise MdxParserError("MDX parser returned an invalid batch item")
        identifier = raw["id"]
        if identifier not in documents or identifier in parsed or identifier in errors:
            raise MdxParserError("MDX parser returned an unexpected batch item")
        if raw.get("ok") is True:
            parsed[identifier] = _parse_payload(raw.get("result"), documents[identifier])
        elif raw.get("ok") is False and isinstance(raw.get("error"), str):
            errors[identifier] = raw["error"]
        else:
            raise MdxParserError("MDX parser returned an invalid batch state")
    if set(parsed) | set(errors) != set(documents):
        raise MdxParserError("MDX parser did not account for every document")
    return parsed, errors


def parse_mdx(text: str) -> MdxDocument:
    parsed, errors = parse_mdx_documents({"document.mdx": text})
    if errors:
        raise MdxParserError(
            f"MDX syntax is not structurally valid: {errors['document.mdx']}"
        )
    return parsed["document.mdx"]
