"""Static look-ahead lint for strategy source code (AST, no execution)."""

from __future__ import annotations

import ast
from typing import Any

_BFILL_METHODS = {"bfill", "backfill"}
_FIT_METHODS = {"fit", "fit_transform", "polyfit"}
_GROUP_AGGS = {"last", "max", "min", "mean", "sum", "std", "median", "size", "count", "nunique"}
_CUM_METHODS = {"cummax", "cummin", "cumsum", "cumprod", "accumulate"}
_FORWARD_REINDEX = {"bfill", "backfill", "nearest"}
_WINDOW_METHODS = {"rolling", "expanding", "ewm"}
_STAT_METHODS = {"mean", "std", "var", "min", "max", "median", "quantile", "sum", "idxmax", "idxmin", "argmax", "argmin"}
_NUMPY_STATS = {"mean", "std", "var", "min", "max", "median", "percentile", "quantile", "sum", "argmax", "argmin", "nanmean", "nanstd"}
_POSITIONAL = {"iloc", "iat", "values"}
_PERIOD_METHODS = {"diff", "pct_change"}
_SAFE_INTERPOLATE = {"pad", "ffill"}
_FORWARD_ASOF = {"forward", "nearest"}
_MODULES = {"np", "numpy", "math", "statistics", "pd", "pandas"}
# Filters that centre the window (or run forwards and backwards) by default.
_CENTERED_FILTERS = {"filtfilt", "sosfiltfilt", "savgol_filter", "gaussian_filter1d", "uniform_filter1d", "medfilt"}
_TRANSFORMS = {"fft", "rfft", "fftn", "rfftn", "dct", "hilbert", "detrend"}
_FULL_RANKS = {"qcut", "argsort"}
_BUILTIN_STATS = {"max", "min", "sum", "sorted"}
_FORWARD_INDEXER = "FixedForwardWindowIndexer"
_CONVOLVE = {"convolve", "correlate"}


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


def _on_groupby(node: ast.AST) -> bool:
    """True when ``node`` is a chain that starts from a ``.groupby(...)`` call."""
    while isinstance(node, ast.Attribute | ast.Subscript | ast.Call):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "groupby":
                return True
            node = node.func
        else:
            node = node.value
    return False


def _is_true(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_false(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _is_str(node: ast.AST | None, values: set[str]) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in values


class _Visitor(ast.NodeVisitor):
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.findings: list[dict[str, Any]] = []
        # Group aggregates followed by a positive shift use completed groups only.
        self._shifted_aggs: set[int] = set()

    def _add(self, node: ast.AST, rule: str, severity: str, message: str) -> None:
        line = int(getattr(node, "lineno", 0))
        if any(f["rule"] == rule and f["line"] == line for f in self.findings):
            return  # one finding per rule and line (e.g. nested argsort calls)
        snippet = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.findings.append(
            {"rule": rule, "severity": severity, "line": line, "message": message, "snippet": snippet}
        )

    @staticmethod
    def _negative_arg(call: ast.Call, pos: int, name: str) -> bool:
        arg = call.args[pos] if len(call.args) > pos else _kw(call, name)
        val = _const_number(arg)
        return val is not None and val < 0

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
                if self._negative_arg(node, 0, "periods"):
                    self._add(node, "negative_shift", "fail", "shift with a negative period reads future bars")
                elif isinstance(node.func.value, ast.Call):
                    self._shifted_aggs.add(id(node.func.value))
            elif attr in _PERIOD_METHODS:
                if self._negative_arg(node, 0, "periods"):
                    self._add(node, "negative_period", "fail", f"{attr} with a negative period compares with future bars")
            elif attr == "roll":
                if self._negative_arg(node, 1, "shift"):
                    self._add(node, "negative_roll", "fail", "roll with a negative shift pulls future values into the past")
            elif attr == "merge_asof" and _is_str(_kw(node, "direction"), _FORWARD_ASOF):
                self._add(node, "forward_asof", "fail", "merge_asof direction forward/nearest joins future rows")
            elif attr == "interpolate" and not _is_str(_kw(node, "method"), _SAFE_INTERPOLATE):
                self._add(node, "interpolate", "fail", "interpolate uses the next known value (future) unless method='ffill'")
            elif attr in _BFILL_METHODS:
                self._add(node, "backward_fill", "fail", "backward fill copies future values into the past")
            elif attr == "fillna" and _is_str(_kw(node, "method"), _BFILL_METHODS):
                self._add(node, "backward_fill", "fail", "fillna(method='bfill') copies future values into the past")
            elif attr == "gradient":
                self._add(node, "central_difference", "fail", "np.gradient uses central differences: bar t reads bar t + 1")
            elif attr in _CONVOLVE and _is_str(_kw(node, "mode") or (node.args[2] if len(node.args) > 2 else None), {"same"}):
                self._add(node, "centered_filter", "fail", f"{attr}(mode='same') centres the kernel on each bar and mixes in future bars")
            elif attr in _CENTERED_FILTERS:
                self._add(node, "centered_filter", "fail", f"{attr} is centred or zero-phase: each output depends on later bars")
            elif attr in _TRANSFORMS:
                self._add(node, "full_sample_transform", "warn", f"{attr} over the whole series mixes every bar with future bars")
            elif attr == "reindex" and _is_str(_kw(node, "method"), _FORWARD_REINDEX):
                self._add(node, "backward_fill", "fail", "reindex with method bfill/nearest takes values from later rows")
            elif attr == "cumcount" and _is_false(_kw(node, "ascending")):
                self._add(node, "reverse_count", "fail", "cumcount(ascending=False) counts the rows still to come")
            elif attr in _CUM_METHODS and (
                _is_reversed(node.func.value) or (node.args and _is_reversed(node.args[0]))
            ):
                self._add(node, "reversed_cumulative", "fail", f"{attr} over a reversed series accumulates future values")
            elif attr in _GROUP_AGGS and _on_groupby(node.func.value):
                if id(node) not in self._shifted_aggs:
                    self._add(node, "group_aggregate", "warn", f"groupby().{attr}() includes later rows of each group; shift(1) to use completed groups")
            elif attr == "sort_values" and not node.args and _kw(node, "by") is None:
                self._add(node, "full_sample_rank", "warn", "sort_values over the whole series orders bars by future values too")
            elif attr == _FORWARD_INDEXER:
                self._add(node, "forward_window", "fail", "FixedForwardWindowIndexer makes rolling windows look at the next bars")
            elif attr == "tail":
                self._add(node, "last_row", "fail", "tail() reads the last (future) bars of the dataset")
            elif attr == "sort" and isinstance(node.func.value, ast.Name) and node.func.value.id in ("np", "numpy"):
                self._add(node, "full_sample_rank", "warn", "np.sort over the whole array orders bars by future values too")
            elif attr == "cut" and isinstance(node.args[1] if len(node.args) > 1 else _kw(node, "bins"), ast.Constant):
                self._add(node, "full_sample_rank", "warn", "pd.cut with a bin count takes edges from the whole-series min and max")
            elif attr in _FULL_RANKS:
                self._add(node, "full_sample_rank", "warn", f"{attr} ranks bars against the whole sample, future included")
            elif attr in _FIT_METHODS:
                self._add(node, "full_sample_fit", "warn", "model fit on the whole series leaks future statistics unless done walk-forward")
            elif attr in _WINDOW_METHODS and _is_reversed(node.func.value):
                self._add(node, "reversed_window", "fail", "window over a reversed series looks into the future")
            elif attr == "rank" and not self._on_window(node.func.value):
                self._add(node, "full_sample_rank", "warn", "rank over the whole series compares bars with future values")
            elif (
                attr in _NUMPY_STATS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("np", "numpy")
                and node.args
                and not isinstance(node.args[0], ast.Call | ast.Constant | ast.List | ast.Tuple)
            ):
                self._add(node, "full_sample_stat", "warn", f"np.{attr} over a whole array includes future bars")
            elif attr in _STAT_METHODS and self._is_series_ref(node.func.value):
                self._add(node, "full_sample_stat", "warn", "whole-series statistic includes future bars (use rolling/expanding)")
            elif attr == "transform" and node.args and _is_str(node.args[0], _GROUP_AGGS):
                self._add(node, "group_aggregate", "warn", "group aggregate broadcasts values from later rows of the same group")
        elif isinstance(node.func, ast.Name):
            name = node.func.id
            if name == _FORWARD_INDEXER:
                self._add(node, "forward_window", "fail", "FixedForwardWindowIndexer makes rolling windows look at the next bars")
            elif name in _BUILTIN_STATS and len(node.args) == 1 and not node.keywords and self._is_series_ref(node.args[0]):
                self._add(node, "full_sample_stat", "warn", f"built-in {name}() over a whole column includes future bars")
        if _is_true(_kw(node, "center")):
            self._add(node, "centered_window", "fail", "center=True windows include future bars")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        idx = node.slice
        target = node.value
        is_positional = (isinstance(target, ast.Attribute) and target.attr in _POSITIONAL) or (
            isinstance(target, ast.Call) and isinstance(target.func, ast.Attribute) and target.func.attr == "to_numpy"
        )
        last = _const_number(idx)
        if is_positional and last is not None and last < 0:
            self._add(node, "last_row", "fail", "indexing from the end reads the last (future) bars of the dataset")
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
