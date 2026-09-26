"""Static look-ahead lint for strategy source code (AST, no execution)."""

from __future__ import annotations

import ast
from typing import Any

_BFILL_METHODS = {"bfill", "backfill"}
_FIT_METHODS = {"fit", "fit_transform"}


def _const_number(node: ast.AST | None) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _const_number(node.operand)
        return -inner if inner is not None else None
    return None


def _kw(call: ast.Call, name: str) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_true(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_str(node: ast.AST | None, values: set[str]) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in values


class _Visitor(ast.NodeVisitor):
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.findings: list[dict[str, Any]] = []

    def _add(self, node: ast.AST, rule: str, severity: str, message: str) -> None:
        line = int(getattr(node, "lineno", 0))
        snippet = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.findings.append(
            {"rule": rule, "severity": severity, "line": line, "message": message, "snippet": snippet}
        )

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr == "shift":
                arg = node.args[0] if node.args else _kw(node, "periods")
                val = _const_number(arg)
                if val is not None and val < 0:
                    self._add(node, "negative_shift", "fail", "shift with a negative period reads future bars")
            elif attr in _BFILL_METHODS:
                self._add(node, "backward_fill", "fail", "backward fill copies future values into the past")
            elif attr == "fillna" and _is_str(_kw(node, "method"), _BFILL_METHODS):
                self._add(node, "backward_fill", "fail", "fillna(method='bfill') copies future values into the past")
            elif attr in _FIT_METHODS:
                self._add(node, "full_sample_fit", "warn", "model fit on the whole series leaks future statistics unless done walk-forward")
        if _is_true(_kw(node, "center")):
            self._add(node, "centered_window", "fail", "center=True windows include future bars")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        idx = node.slice
        if isinstance(idx, ast.BinOp) and isinstance(idx.op, ast.Add):
            step = _const_number(idx.right)
            if step is not None and step > 0:
                self._add(node, "forward_index", "warn", "indexing at i + k may read a future bar")
        self.generic_visit(node)


def lint_source(source: str) -> dict[str, Any]:
    """Return look-ahead findings for Python ``source``.

    Status is ``fail`` when any fail-severity rule matches, ``warn`` for
    warn-only findings, ``pass`` otherwise, ``skip`` if the code does not parse.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"status": "skip", "findings": [], "error": f"syntax error: {exc.msg} (line {exc.lineno})"}
    visitor = _Visitor(source.splitlines())
    visitor.visit(tree)
    severities = {f["severity"] for f in visitor.findings}
    status = "fail" if "fail" in severities else ("warn" if severities else "pass")
    return {"status": status, "findings": visitor.findings}


__all__ = ["lint_source"]
