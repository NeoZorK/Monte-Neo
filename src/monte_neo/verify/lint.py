"""Static look-ahead lint for strategy source code (AST, no execution)."""

from __future__ import annotations

import ast
from typing import Any

_BFILL_METHODS = {"bfill", "backfill"}
_FIT_METHODS = {"fit", "fit_transform", "polyfit"}
_GROUP_AGGS = {"last", "max", "min", "mean", "sum", "std", "median"}
_WINDOW_METHODS = {"rolling", "expanding", "ewm"}
_STAT_METHODS = {"mean", "std", "var", "min", "max", "median", "quantile"}
_MODULES = {"np", "numpy", "math", "statistics", "pd", "pandas"}


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


def _is_reversed(node: ast.AST) -> bool:
    """True for ``x[::-1]`` (a full reverse slice)."""
    if not isinstance(node, ast.Subscript) or not isinstance(node.slice, ast.Slice):
        return False
    sl = node.slice
    return sl.lower is None and sl.upper is None and _const_number(sl.step) == -1.0


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

    @staticmethod
    def _on_window(node: ast.AST) -> bool:
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _WINDOW_METHODS

    @staticmethod
    def _is_series_ref(node: ast.AST) -> bool:
        """A plain column / variable (not a window or module call)."""
        if isinstance(node, ast.Name):
            return node.id not in _MODULES
        return isinstance(node, ast.Subscript | ast.Attribute) and not (
            isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in _MODULES
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
            elif attr in _WINDOW_METHODS and _is_reversed(node.func.value):
                self._add(node, "reversed_window", "fail", "window over a reversed series looks into the future")
            elif attr == "rank" and not self._on_window(node.func.value):
                self._add(node, "full_sample_rank", "warn", "rank over the whole series compares bars with future values")
            elif attr in _STAT_METHODS and self._is_series_ref(node.func.value):
                self._add(node, "full_sample_stat", "warn", "whole-series statistic includes future bars (use rolling/expanding)")
            elif attr == "transform" and node.args and _is_str(node.args[0], _GROUP_AGGS):
                self._add(node, "group_aggregate", "warn", "group aggregate broadcasts values from later rows of the same group")
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
