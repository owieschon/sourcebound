from __future__ import annotations

import ast
import hashlib
import json
from typing import Any

from clean_docs.errors import ExtractionError
from clean_docs.models import EvidenceValue, Provenance, RegionBinding
from clean_docs.snapshot import RepositorySnapshot


def _evaluate(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        keys = []
        for key in node.keys:
            if key is None:
                raise ExtractionError("python-literal mappings cannot contain unpacking")
            keys.append(key)
        return {_evaluate(key): _evaluate(value) for key, value in zip(keys, node.values)}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_evaluate(item) for item in node.elts]
    if isinstance(node, ast.Call):
        if node.args:
            raise ExtractionError("python-literal constructor calls may use keyword arguments only")
        if any(keyword.arg is None for keyword in node.keywords):
            raise ExtractionError("python-literal constructor calls cannot contain unpacking")
        return {keyword.arg: _evaluate(keyword.value) for keyword in node.keywords}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _evaluate(node.operand)
        if isinstance(value, (int, float)):
            return -value if isinstance(node.op, ast.USub) else value
    raise ExtractionError(f"unsupported Python syntax in bound literal: {type(node).__name__}")


def _find_assignment(tree: ast.Module, symbol: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == symbol for target in node.targets):
                return node.value
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == symbol and node.value:
                return node.value
    raise ExtractionError(f"Python symbol not found: {symbol}")


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    if isinstance(value, dict) and all(isinstance(item, dict) for item in value.values()):
        rows = []
        for key, item in value.items():
            row = dict(item)
            row.setdefault("key", key)
            rows.append(row)
        return rows
    raise ExtractionError("markdown-table evidence must be a list or mapping of records")


def extract_python_literal(
    snapshot: RepositorySnapshot, binding: RegionBinding
) -> EvidenceValue:
    if binding.source.symbol is None:
        raise ExtractionError("python-literal source requires a symbol")
    text = snapshot.read_text(binding.source.path)
    try:
        tree = ast.parse(text, filename=binding.source.path.as_posix())
    except SyntaxError as exc:
        raise ExtractionError(f"cannot parse {binding.source.path}: {exc}") from exc
    value = _rows(_evaluate(_find_assignment(tree, binding.source.symbol)))
    normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return EvidenceValue(
        kind="table",
        value=value,
        provenance=Provenance(
            ref=snapshot.label,
            path=binding.source.path.as_posix(),
            locator=binding.source.symbol,
            extractor="python-literal@1",
            digest=digest,
        ),
    )
