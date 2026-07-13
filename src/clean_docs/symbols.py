from __future__ import annotations

import ast
import hashlib

from clean_docs.errors import ExtractionError
from clean_docs.models import EvidenceValue, Provenance, SymbolBinding
from clean_docs.snapshot import RepositorySnapshot


def resolve_symbol(snapshot: RepositorySnapshot, binding: SymbolBinding) -> EvidenceValue:
    text = snapshot.read_text(binding.source.path)
    locator = binding.source.symbol or binding.source.path.as_posix()
    if binding.source.symbol is not None:
        try:
            tree = ast.parse(text, filename=binding.source.path.as_posix())
        except SyntaxError as exc:
            raise ExtractionError(f"cannot parse {binding.source.path}: {exc}") from exc
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        names.update(
            target.id
            for node in ast.walk(tree)
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
                if isinstance(node, ast.AnnAssign)
                else []
            )
            if isinstance(target, ast.Name)
        )
        if binding.source.symbol not in names:
            raise ExtractionError(f"symbol not found: {binding.source.path}:{binding.source.symbol}")
    digest = hashlib.sha256(locator.encode()).hexdigest()
    return EvidenceValue(
        kind="symbol",
        value=locator,
        provenance=Provenance(
            ref=snapshot.label,
            path=binding.source.path.as_posix(),
            locator=locator,
            extractor="symbol@1",
            digest=digest,
        ),
    )
