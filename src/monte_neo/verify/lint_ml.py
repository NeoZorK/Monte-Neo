"""Lint rules for two machine-learning leaks that need the whole function in view.

* ``full_sample_transform``: a scikit-learn style transformer (scaler, PCA, feature selector) fitted on a whole
  feature matrix before any split, so every later row is scaled or selected with statistics of the future.
* ``target_encoding_full``: a group mean of the target (label, forward return) mapped back onto the same rows.

Both are heuristics kept conservative: a ``fit`` whose argument is sliced (``X[:split]``, ``iloc[:n]``, a ``train`` name)
is not flagged.
"""

from __future__ import annotations

import ast
from typing import Any

TRANSFORMERS = {"StandardScaler", "MinMaxScaler", "RobustScaler", "PCA", "SelectKBest", "SelectFromModel"}
FIT_METHODS = {"fit", "fit_transform"}
TARGET_WORDS = ("target", "label", "y_", "fwd", "future")
_SLICE_MARKERS = ("[:", "iloc[:", "train")


def _class_name(node: ast.AST) -> str:
    """Name of the class a ``Call`` constructs (``StandardScaler()`` or ``preprocessing.StandardScaler()``), else ``""``."""
    if isinstance(node, ast.Call):
        func = node.func
        return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    return ""


def _transformer_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _class_name(node.value) in TRANSFORMERS:
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _is_target_column(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and any(w in node.value.lower() for w in TARGET_WORDS)


def _grouped_target(node: ast.AST) -> bool:
    """``<x>.groupby(...)[<target column>]``."""
    if not isinstance(node, ast.Subscript) or not _is_target_column(node.slice):
        return False
    inner: ast.AST = node.value
    while isinstance(inner, ast.Attribute | ast.Call):
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) and inner.func.attr == "groupby":
            return True
        inner = inner.func if isinstance(inner, ast.Call) else inner.value
    return False


def ml_findings(tree: ast.AST, lines: list[str]) -> list[dict[str, Any]]:
    """Findings of ``full_sample_transform`` and ``target_encoding_full`` for a parsed module."""
    found: list[dict[str, Any]] = []
    names = _transformer_names(tree)

    def add(node: ast.AST, rule: str, message: str) -> None:
        line = int(getattr(node, "lineno", 0))
        if any(f["rule"] == rule and f["line"] == line for f in found):
            return
        snippet = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        found.append({"rule": rule, "severity": "warn", "line": line, "message": message, "snippet": snippet})

    mapped = {id(a) for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "map" for a in n.args}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        attr, owner = node.func.attr, node.func.value
        if attr in FIT_METHODS and (_class_name(owner) in TRANSFORMERS or (isinstance(owner, ast.Name) and owner.id in names)) and node.args:
            text = ast.unparse(node.args[0])
            if not any(marker in text for marker in _SLICE_MARKERS):
                add(node, "full_sample_transform",
                    f".{attr}({text}) fits a scaler, PCA or selector on the whole feature matrix: fit it on the training rows only")
        elif attr == "transform" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "mean" and _grouped_target(owner):
            add(node, "target_encoding_full", "a group mean of the target broadcast to every row uses later rows' targets: encode from earlier rows only")
        elif attr == "mean" and id(node) in mapped and _grouped_target(owner):
            add(node, "target_encoding_full", "a group mean of the target mapped back onto the same rows uses later rows' targets: encode from earlier rows only")
    return found


__all__ = ["ml_findings"]
