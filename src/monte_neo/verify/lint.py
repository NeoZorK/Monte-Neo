"""Static look-ahead lint for strategy source code (AST, no execution)."""

from __future__ import annotations

import ast
import copy
from typing import Any

_BFILL_METHODS = {"bfill", "backfill"}
_FIT_METHODS = {"fit", "fit_transform", "polyfit"}
_GROUP_AGGS = {"last", "max", "min", "mean", "sum", "std", "median", "size", "count", "nunique", "agg", "aggregate"}
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
# Cross-validation splitters that train on later data (TimeSeriesSplit is the safe one).
_SPLITTERS = {"KFold", "StratifiedKFold", "GroupKFold", "RepeatedKFold", "ShuffleSplit", "StratifiedShuffleSplit", "GroupShuffleSplit"}
_SHUFFLE_SPLITTERS = {"ShuffleSplit", "StratifiedShuffleSplit", "GroupShuffleSplit"}
# Whole-series methods reported even when called on a derived series (e.g. close.round(-1).mode()).
_WHOLE_STATS = {"describe", "agg", "aggregate", "mode", "value_counts"}
_WHOLE_RANKS = {"nlargest", "nsmallest"}
_CHAIN_BREAKERS = _WINDOW_METHODS | {"groupby", "resample"}
_CONVOLVE = {"convolve", "correlate"}
# Reading data outside df: the probes rewrite df, so data loaded here keeps its future.
_DATA_READERS = {
    "read_csv", "read_parquet", "read_feather", "read_pickle", "read_json", "read_excel", "read_hdf",
    "read_table", "read_fwf", "read_orc", "read_sql", "read_sql_query", "read_sql_table", "read_ipc",
    "read_text", "read_bytes", "loadtxt", "genfromtxt", "fromfile", "memmap",
}
# Pivots are known only after later bars confirm them; a signal on the pivot bar repaints.
_PIVOT_FINDERS = {"find_peaks", "find_peaks_cwt", "argrelextrema", "argrelmax", "argrelmin"}
_HTF_AGGS = {"last", "first", "max", "min", "mean", "sum", "ohlc", "median"}
_NETWORK_MODULES = {"requests", "urllib", "httpx", "aiohttp", "socket", "yfinance", "ccxt", "websocket", "websockets"}


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
    """True for ``x[::-1]`` (a full reverse slice) and ``np.flip(x)``."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "flip"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in ("np", "numpy")
    ):
        return True
    if not isinstance(node, ast.Subscript) or not isinstance(node.slice, ast.Slice):
        return False
    sl = node.slice
    return sl.lower is None and sl.upper is None and _const_number(sl.step) == -1.0


def _on_groupby(node: ast.AST) -> bool:
    """True when ``node`` is a chain that starts from a ``.groupby(...)`` or ``.resample(...)`` call."""
    while isinstance(node, ast.Attribute | ast.Subscript | ast.Call):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("groupby", "resample"):
                return True
            node = node.func
        else:
            node = node.value
    return False


def _on_resample(node: ast.AST) -> bool:
    """True when ``node`` is ``x.resample(...)`` (the call whose aggregate is taken)."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "resample"


# Rules about one future-reading value: harmless when that value is assigned and never read.
_FUTURE_VALUE_RULES = {"negative_shift", "negative_period", "negative_roll", "centered_window", "centered_filter", "backward_fill", "forward_window", "central_difference"}
_ORIGIN_FILTERS = {"uniform_filter1d", "minimum_filter1d", "maximum_filter1d"}


def _trailing_ndimage_window(call: ast.Call, attr: str) -> bool:
    """``uniform_filter1d(x, size, origin=o)`` with ``o >= (size - 1) // 2``: the window ends at the current bar."""
    if attr not in _ORIGIN_FILTERS:
        return False
    size = _const_number(call.args[1] if len(call.args) > 1 else _kw(call, "size"))
    origin = _const_number(_kw(call, "origin") if _kw(call, "origin") is not None else (call.args[3] if len(call.args) > 3 else None))
    return size is not None and origin is not None and size >= 1 and origin >= (int(size) - 1) // 2


def _dead_assignment_lines(tree: ast.AST) -> set[int]:
    """Lines of ``name = <value>`` statements, and of private ``_helper`` functions, that nothing in the module reads."""
    loaded = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    loaded |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    loaded |= {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}  # getattr(x, "_name"), globals()["_name"]
    dead: set[int] = set()
    if isinstance(tree, ast.Module):
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("_") and not node.name.startswith("__") and node.name not in loaded:
                dead.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id not in loaded:
            dead.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return dead


def _is_timestamp_column(node: ast.AST | None) -> bool:
    """``"timestamp"``, ``df["timestamp"]`` or ``df.timestamp``: the exact bar time, not a derived date."""
    if isinstance(node, ast.Constant):
        return node.value == "timestamp"
    if isinstance(node, ast.Subscript):
        return _is_timestamp_column(node.slice)
    return isinstance(node, ast.Attribute) and node.attr == "timestamp"


def _grouped_by_timestamp(node: ast.AST) -> bool:
    """A chain grouped by the exact timestamp: every group is one cross-section of a universe,
    so ranks and aggregates compare symbols at the same moment (no later rows)."""
    while isinstance(node, ast.Attribute | ast.Subscript | ast.Call):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "groupby":
                key = node.args[0] if node.args else _kw(node, "by")
                return _is_timestamp_column(key)
            node = node.func
        else:
            node = node.value
    return False


def _is_series_chain(node: ast.AST) -> bool:
    """A column or a chain of element-wise calls on it, with no window / groupby / resample step."""
    while isinstance(node, ast.Attribute | ast.Subscript | ast.Call):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in _CHAIN_BREAKERS:
                return False
            node = node.func
        else:
            node = node.value
    return isinstance(node, ast.Name) and node.id not in _MODULES


class _InlineConstants(ast.NodeTransformer):
    """Replace names assigned a constant exactly once (``horizon = -1``) by that constant."""

    def __init__(self, tree: ast.AST) -> None:
        stores: dict[str, int] = {}
        values: dict[str, ast.AST] = {}
        params: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                stores[node.id] = stores.get(node.id, 0) + 1
            elif isinstance(node, ast.arg):
                params.add(node.arg)
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and (isinstance(node.value, ast.Constant) or _const_number(node.value) is not None)
            ):
                values[node.targets[0].id] = node.value
        self.consts = {k: v for k, v in values.items() if stores.get(k) == 1 and k not in params}

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Load) and node.id in self.consts:
            return ast.copy_location(copy.deepcopy(self.consts[node.id]), node)
        return node


def _is_window_slice(node: ast.AST) -> bool:
    """``x[a:b]`` with a variable upper bound: a moving window such as ``c[i - 20:i]``.

    A constant bound (``c[:1000]``) is a fixed block of the dataset, which is the
    future for earlier bars, so it stays a whole-sample statistic.
    """
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Slice)
        and node.slice.upper is not None
        and _const_number(node.slice.upper) is None
    )


def _window_functions(tree: ast.AST) -> tuple[set[str], set[int]]:
    """Functions and lambdas passed to ``rolling(...).apply`` (they only see one window)."""
    names: set[str] = set()
    lambdas: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"apply", "agg", "aggregate"}
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Attribute)
            and node.func.value.func.attr in _WINDOW_METHODS
            and node.args
        ):
            if isinstance(node.args[0], ast.Name):
                names.add(node.args[0].id)
            elif isinstance(node.args[0], ast.Lambda):
                lambdas.add(id(node.args[0]))
    return names, lambdas


def _fits_a_subset(call: ast.Call) -> bool:
    """``fit(X[train], y[train])``: the model is trained on a chosen slice, as walk-forward code does.

    Whether that slice ends before the bars the model predicts is for the probes to decide; the
    lint only warns when the model is fitted on a whole named array.
    """
    return bool(call.args) and isinstance(call.args[0], ast.Subscript)


_CACHING_DECORATORS = {"lru_cache", "cache", "cached_property", "memoize", "cached"}
_TRAIN_METHODS = {"fit", "fit_transform", "partial_fit", "train"}


def _is_true(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_false(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _is_str(node: ast.AST | None, values: set[str]) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in values


class _Visitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], window_names: set[str] | None = None, window_lambdas: set[int] | None = None) -> None:
        self.lines = lines
        self.findings: list[dict[str, Any]] = []
        # Inside a rolling().apply function "whole series" means one window.
        self._window_names = window_names or set()
        self._window_lambdas = window_lambdas or set()
        self._in_window = 0
        # Group aggregates followed by a positive shift use completed groups only.
        self._shifted_aggs: set[int] = set()
        self._functions = 0  # depth of function bodies: module level is 0
        self._shifted: set[int] = set()  # resample aggregates that are shifted afterwards

    def _add(self, node: ast.AST, rule: str, severity: str, message: str) -> None:
        if self._in_window and rule.startswith("full_sample"):
            return
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

    def _windowed(self, node: ast.AST) -> Any:
        self._in_window += 1
        self.generic_visit(node)
        self._in_window -= 1

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        return self._windowed(node) if id(node) in self._window_lambdas else self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Any:
        self._repaint_name(node, node.name)
        for deco in node.decorator_list:
            target = deco.func if isinstance(deco, ast.Call) else deco
            name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
            if name in _CACHING_DECORATORS:
                self._add(
                    node, "cached_signal", "warn",
                    f"@{name} keeps results between calls: a cached answer computed on the whole table "
                    "passes the truncation probe without being causal",
                )
        self._functions += 1
        try:
            return self._windowed(node) if node.name in self._window_names else self.generic_visit(node)
        finally:
            self._functions -= 1

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815 (the name is ast.NodeVisitor's dispatch key)

    def _repaint_name(self, node: ast.AST, name: str) -> None:
        low = name.lower().replace("_", "")
        if "zigzag" in low:
            self._add(node, "repaint_zigzag", "warn", f"{name}: a ZigZag leg is redrawn until a later bar confirms it, so its signal repaints; use the confirmed leg, shifted by the confirmation lag")
        if low == "lookaheadon":
            self._add(node, "lookahead_on", "warn", "lookahead_on shows a higher-timeframe bar before it closed")

    def visit_Global(self, node: ast.Global) -> Any:
        self._add(
            node, "global_state", "warn",
            "a global variable survives between calls: state kept from the full table can leak into truncated runs",
        )

    @staticmethod
    def _is_series_ref(node: ast.AST) -> bool:
        """A plain column / variable (not a window or module call)."""
        if _is_window_slice(node):
            return False
        if isinstance(node, ast.Name):
            return node.id not in _MODULES
        return isinstance(node, ast.Subscript | ast.Attribute) and not (
            isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in _MODULES
        )

    def _external(self, node: ast.AST, what: str) -> None:
        self._add(node, "external_data", "fail", f"{what} reads data outside df, where the look-ahead probes cannot see it")

    def visit_If(self, node: ast.If) -> Any:
        # A local `if __name__ == "__main__":` run is not part of signal(); lint only its else branch.
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and _is_str(test.comparators[0] if test.comparators else None, {"__main__"})
        ):
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            if alias.name.split(".")[0] in _NETWORK_MODULES:
                self._external(node, f"import {alias.name}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module and node.module.split(".")[0] in _NETWORK_MODULES:
            self._external(node, f"from {node.module} import")

    def _split_rules(self, node: ast.Call) -> None:
        """Train/test splits that mix the future into training (shuffled splits, k-fold without time order)."""
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        shuffle = _kw(node, "shuffle")
        if name == "train_test_split" and not _is_false(shuffle):
            severity = "fail" if _is_true(shuffle) else "warn"
            how = "shuffle=True" if _is_true(shuffle) else "shuffles by default"
            self._add(node, "shuffled_split", severity, f"train_test_split {how}: rows of a time series are split at random, so training sees the future; use shuffle=False or a time split")
        elif name in _SPLITTERS:
            random = _is_true(shuffle) or name in _SHUFFLE_SPLITTERS
            self._add(
                node, "kfold_split", "fail" if random else "warn",
                f"{name} {'shuffles rows' if random else 'trains on later folds'} of a time series; use TimeSeriesSplit with a gap (embargo)",
            )

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            self._external(node, "open()")
        if isinstance(node.func, ast.Attribute) and (
            node.func.attr in _DATA_READERS
            or (node.func.attr == "load" and isinstance(node.func.value, ast.Name) and node.func.value.id in {"np", "numpy"})
        ):
            self._external(node, f"{node.func.attr}()")
        self._split_rules(node)
        if _kw(node, "lookahead") is not None and (
            _is_true(_kw(node, "lookahead")) or (isinstance(_kw(node, "lookahead"), ast.Constant) and str(_kw(node, "lookahead").value).lower() in ("on", "lookahead_on"))  # type: ignore[union-attr]
        ):
            self._add(node, "lookahead_on", "warn", "lookahead on shows a higher-timeframe bar before it closed: its value is future information on every lower-timeframe bar")
        if isinstance(node.func, ast.Attribute) and node.func.attr == "shift":
            inner = node.func.value
            while isinstance(inner, ast.Call | ast.Attribute):
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) and inner.func.attr in _HTF_AGGS and _on_resample(inner.func.value):
                    self._shifted.add(id(inner))
                inner = inner.func if isinstance(inner, ast.Call) else inner.value
        called = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if called in _PIVOT_FINDERS:
            self._add(node, "unconfirmed_pivot", "warn", f"{called} finds pivots that later bars confirm: a signal on the pivot bar repaints; shift it by the confirmation lag")
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in _HTF_AGGS
            and _on_resample(node.func.value)
            and id(node) not in self._shifted
        ):
            self._add(node, "htf_without_shift", "warn", "a higher-timeframe bar is used on lower-timeframe bars before it closed: shift(1) the resampled series before aligning it back")
        if self._functions == 0 and isinstance(node.func, ast.Attribute) and node.func.attr in _TRAIN_METHODS:
            self._add(
                node, "import_time_fit", "warn",
                f".{node.func.attr}() runs when the module loads, on data the look-ahead probes never change: "
                "a model fitted on the whole file carries the future into every later call",
            )
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
            elif attr in _CENTERED_FILTERS and not _trailing_ndimage_window(node, attr):
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
            elif attr in _GROUP_AGGS and _on_groupby(node.func.value) and not _grouped_by_timestamp(node.func.value):
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
            elif attr == "interp" and isinstance(node.func.value, ast.Name) and node.func.value.id in ("np", "numpy"):
                self._add(node, "interpolate", "fail", "np.interp draws a line to the next known point (future) across gaps")
            elif attr in _WHOLE_RANKS and _is_series_chain(node.func.value):
                self._add(node, "full_sample_rank", "warn", f"{attr} over the whole series picks bars by future values too")
            elif attr in _WHOLE_STATS and _is_series_chain(node.func.value):
                self._add(node, "full_sample_stat", "warn", f"{attr}() over the whole series includes future bars")
            elif attr in _FULL_RANKS:
                self._add(node, "full_sample_rank", "warn", f"{attr} ranks bars against the whole sample, future included")
            elif attr in _FIT_METHODS and not _fits_a_subset(node):
                self._add(node, "full_sample_fit", "warn", "model fit on the whole series leaks future statistics unless done walk-forward")
            elif attr in _WINDOW_METHODS and _is_reversed(node.func.value):
                self._add(node, "reversed_window", "fail", "window over a reversed series looks into the future")
            elif attr == "rank" and not self._on_window(node.func.value) and not _grouped_by_timestamp(node.func.value):
                self._add(node, "full_sample_rank", "warn", "rank over the whole series compares bars with future values")
            elif (
                attr in _NUMPY_STATS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("np", "numpy")
                and node.args
                and not isinstance(node.args[0], ast.Call | ast.Constant | ast.List | ast.Tuple)
                and not _is_window_slice(node.args[0])
            ):
                self._add(node, "full_sample_stat", "warn", f"np.{attr} over a whole array includes future bars")
            elif attr in _STAT_METHODS and self._is_series_ref(node.func.value):
                self._add(node, "full_sample_stat", "warn", "whole-series statistic includes future bars (use rolling/expanding)")
            elif attr == "transform" and node.args and _is_str(node.args[0], _GROUP_AGGS) and not _grouped_by_timestamp(node.func.value):
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
    tree = _InlineConstants(tree).visit(tree)
    visitor = _Visitor(source.splitlines(), *_window_functions(tree))
    visitor.visit(tree)
    dead = _dead_assignment_lines(tree)
    for finding in visitor.findings:
        if finding["severity"] == "fail" and finding["line"] in dead and finding["rule"] in _FUTURE_VALUE_RULES:
            # A future value that is assigned and never read cannot reach the signal; the dynamic probes still judge the strategy.
            finding["severity"] = "warn"
            finding["message"] += " (the value is assigned to a name that is never read)"
    severities = {f["severity"] for f in visitor.findings}
    status = "fail" if "fail" in severities else ("warn" if severities else "pass")
    return {"status": status, "findings": visitor.findings}


__all__ = ["lint_source"]
