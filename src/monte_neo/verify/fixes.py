"""Suggested rewrites that make a leaking strategy causal.

``suggest_fixes(source)`` finds the patterns the verifier reports most often and rewrites them so that bar ``t``
reads only bars up to ``t``: ``shift(-k)`` becomes ``shift(k)``, a centred window becomes a trailing one,
``bfill`` becomes ``ffill``, a whole-sample statistic becomes its expanding version and a group aggregate over the
future of its group becomes the running aggregate.

The rewrite keeps the *shape* of the strategy, not its meaning: a signal that was built from the future is now
built from the past, so its numbers change. Treat the patch as the answer to "what would a causal version look
like", verify it, and re-think the idea. Comments are not kept (the source is regenerated from its syntax tree).
"""

from __future__ import annotations

import ast
import difflib
from typing import Any

from monte_neo.verify.lint import lint_source

_WINDOWED = {"rolling", "expanding", "ewm", "groupby", "cummax", "cummin", "cumsum", "cumprod", "resample", "tail", "head", "iloc", "loc", "nlargest", "nsmallest", "sort_values", "to_numpy", "values", "tolist"}
_WHOLE_STATS = {"mean", "std", "var", "max", "min", "median", "skew", "kurt"}
_GROUP_CUM = {"max": "cummax", "min": "cummin", "sum": "cumsum", "prod": "cumprod"}
_MODULES = {"np", "numpy", "pd", "pandas", "scipy", "math"}


def _negative(node: ast.AST | None) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
        return isinstance(node.operand.value, int | float)
    return isinstance(node, ast.Constant) and isinstance(node.value, int | float) and node.value < 0


def _flip(node: ast.expr) -> ast.expr:
    if isinstance(node, ast.UnaryOp):
        return node.operand
    assert isinstance(node, ast.Constant)
    return ast.Constant(value=-node.value)


def _chain_has(node: ast.AST, names: set[str]) -> bool:
    while isinstance(node, ast.Call | ast.Attribute | ast.Subscript):
        if isinstance(node, ast.Attribute) and node.attr in names:
            return True
        node = node.func if isinstance(node, ast.Call) else node.value
    return False


def _series_like(node: ast.AST) -> bool:
    """A column, a name or a method chain on one (not a module call such as ``np.mean``)."""
    if isinstance(node, ast.Subscript):
        return True
    if isinstance(node, ast.Name):
        return node.id not in _MODULES
    if isinstance(node, ast.Call):
        return isinstance(node.func, ast.Attribute) and _series_like(node.func.value)
    return isinstance(node, ast.Attribute) and _series_like(node.value)


class _Causalize(ast.NodeTransformer):
    def __init__(self) -> None:
        self.changes: list[dict[str, Any]] = []
        self._apply_depth = 0

    def _note(self, node: ast.AST, rule: str, before: str, after: str, why: str) -> None:
        self.changes.append({"line": int(getattr(node, "lineno", 0)), "rule": rule, "before": before, "after": after, "note": why})

    def visit_Call(self, node: ast.Call) -> ast.AST:
        before = ast.unparse(node)
        is_apply = isinstance(node.func, ast.Attribute) and node.func.attr in {"apply", "agg", "aggregate", "transform"} and _chain_has(node.func.value, {"rolling", "expanding"})
        self._apply_depth += int(is_apply)
        self.generic_visit(node)
        self._apply_depth -= int(is_apply)
        if not isinstance(node.func, ast.Attribute):
            return node
        attr, target = node.func.attr, node.func.value

        if attr in {"shift", "pct_change", "diff"} and (node.args or node.keywords):
            arg = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "periods"), None)
            if _negative(arg):
                new = _flip(arg)
                if node.args:
                    node.args[0] = new
                else:
                    next(k for k in node.keywords if k.arg == "periods").value = new
                self._note(node, "negative_shift", before, ast.unparse(node), "looks back instead of forward")
            return node
        if attr in {"rolling", "ewm"}:
            kept = [k for k in node.keywords if not (k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value is True)]
            if len(kept) != len(node.keywords):
                node.keywords = kept
                self._note(node, "centered_window", before, ast.unparse(node), "the window now ends at the current bar")
            return node
        if attr == "bfill" and _series_like(target):
            node.func.attr = "ffill"
            self._note(node, "backward_fill", before, ast.unparse(node), "fills from the past, not from the next value")
            return node
        if attr == "interpolate" and _series_like(target):
            node.func.attr, node.args, node.keywords = "ffill", [], []
            self._note(node, "interpolate", before, ast.unparse(node), "holds the last known value instead of drawing a line to the next one")
            return node
        if self._apply_depth or not _series_like(target) or _chain_has(target, _WINDOWED):
            return node
        if attr in _WHOLE_STATS and not node.args and not node.keywords:
            node.func.value = ast.Call(func=ast.Attribute(value=target, attr="expanding", ctx=ast.Load()), args=[], keywords=[])
            self._note(node, "whole_sample_statistic", before, ast.unparse(node), "uses the bars seen so far, not the whole table")
        elif attr == "quantile" and node.args:
            node.func.value = ast.Call(func=ast.Attribute(value=target, attr="expanding", ctx=ast.Load()), args=[], keywords=[])
            self._note(node, "whole_sample_statistic", before, ast.unparse(node), "uses the bars seen so far, not the whole table")
        elif attr == "rank":
            node.func.value = ast.Call(func=ast.Attribute(value=target, attr="expanding", ctx=ast.Load()), args=[], keywords=[])
            self._note(node, "whole_sample_rank", before, ast.unparse(node), "ranks against the bars seen so far")
        elif attr == "transform" and node.args and isinstance(target, ast.Call) and isinstance(target.func, ast.Attribute) and target.func.attr == "groupby":
            how = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
            if how in _GROUP_CUM:
                return self._group_note(node, before, ast.Call(func=ast.Attribute(value=target, attr=_GROUP_CUM[how], ctx=ast.Load()), args=[], keywords=[]))
            if how == "last":  # the running "last value of the group" is the current value
                return self._group_note(node, before, target.func.value)
        return node

    def _group_note(self, node: ast.AST, before: str, replacement: ast.expr) -> ast.expr:
        self._note(node, "group_aggregate", before, ast.unparse(replacement), "uses the group's bars seen so far, not the whole group")
        return replacement


def suggest_fixes(source: str) -> dict[str, Any]:
    """``{"changes", "patched", "diff", "remaining"}``: the rewrites, the new source, a unified diff and the lint findings left."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"changes": [], "patched": source, "diff": "", "remaining": [], "error": f"syntax error: {exc.msg} (line {exc.lineno})"}
    fixer = _Causalize()
    patched_tree = ast.fix_missing_locations(fixer.visit(tree))
    patched = ast.unparse(patched_tree) + "\n" if fixer.changes else source
    diff = "".join(difflib.unified_diff(source.splitlines(True), patched.splitlines(True), "strategy.py", "strategy.causal.py")) if fixer.changes else ""
    remaining = lint_source(patched)["findings"] if fixer.changes else lint_source(source)["findings"]
    return {"changes": fixer.changes, "patched": patched, "diff": diff, "remaining": remaining}


__all__ = ["suggest_fixes"]
