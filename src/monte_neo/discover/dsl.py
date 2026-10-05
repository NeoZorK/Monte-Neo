"""A causal grammar for indicators: trees that can only read the past.

Every operation looks back (trailing windows, lags of one bar or more), so a tree cannot read the future by
construction. The same tree is evaluated on pandas series and written out as a readable ``signal(df)``; a test
checks that both agree. Nothing here evaluates text: a tree is data, never code that is executed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

Node = tuple  # ("col", name) | ("const", value) | (op, params, children)
COLUMNS = ("open", "high", "low", "close", "volume", "ret", "range")
WINDOWS = (3, 5, 8, 12, 20, 30, 50, 80, 120)
RULE_WINDOWS = (10, 30, 90)

# op -> (arity, number of window parameters, pandas function, source template)
WINDOWED: dict[str, tuple[Callable[..., pd.Series], str]] = {
    "sma": (lambda x, n: x.rolling(n).mean(), "{x}.rolling({n}).mean()"),
    "ema": (lambda x, n: x.ewm(span=n, adjust=False).mean(), "{x}.ewm(span={n}, adjust=False).mean()"),
    "std": (lambda x, n: x.rolling(n).std(), "{x}.rolling({n}).std()"),
    "rmax": (lambda x, n: x.rolling(n).max(), "{x}.rolling({n}).max()"),
    "rmin": (lambda x, n: x.rolling(n).min(), "{x}.rolling({n}).min()"),
    "lag": (lambda x, n: x.shift(n), "{x}.shift({n})"),
    "diff": (lambda x, n: x.diff(n), "{x}.diff({n})"),
    "roc": (lambda x, n: x / x.shift(n) - 1.0, "({x} / {x}.shift({n}) - 1.0)"),
    "zscore": (lambda x, n: (x - x.rolling(n).mean()) / x.rolling(n).std(), "(({x} - {x}.rolling({n}).mean()) / {x}.rolling({n}).std())"),
}
UNARY: dict[str, tuple[Callable[..., pd.Series], str]] = {
    "neg": (lambda x: -x, "(-{x})"),
    "abs": (lambda x: x.abs(), "{x}.abs()"),
    "sign": (lambda x: np.sign(x), "np.sign({x})"),
}
BINARY: dict[str, tuple[Callable[..., pd.Series], str]] = {
    "add": (lambda a, b: a + b, "({a} + {b})"),
    "sub": (lambda a, b: a - b, "({a} - {b})"),
    "mul": (lambda a, b: a * b, "({a} * {b})"),
    "div": (lambda a, b: a / b.where(b.abs() > 1e-12), "({a} / {b}.where({b}.abs() > 1e-12))"),
}
COMMUTATIVE = {"add", "mul"}
LEAF_SOURCE = {
    "open": 'df["open"]', "high": 'df["high"]', "low": 'df["low"]', "close": 'df["close"]', "volume": 'df["volume"]',
    "ret": 'df["close"].pct_change()', "range": '((df["high"] - df["low"]) / df["close"])',
}


def leaf(name: str) -> Node:
    return ("col", name)


def op(name: str, children: tuple[Node, ...], params: tuple[int, ...] = ()) -> Node:
    if name not in WINDOWED and name not in UNARY and name not in BINARY:
        raise ValueError(f"unknown operation {name!r}")
    return (name, params, children)


def key(node: Node) -> str:
    """Canonical text of a tree: commutative operands are sorted, so a + b and b + a are one variant."""
    if node[0] == "col":
        return node[1]
    name, params, children = node
    parts = [key(c) for c in children]
    if name in COMMUTATIVE:
        parts.sort()
    return f"{name}{list(params) if params else ''}({', '.join(parts)})"


def depth(node: Node) -> int:
    return 1 if node[0] == "col" else 1 + max(depth(c) for c in node[2])


def lookback(node: Node) -> int:
    """Bars before the first value of the tree exists (an upper bound)."""
    if node[0] == "col":
        return 1 if node[1] in ("ret",) else 0
    name, params, children = node
    inner = max(lookback(c) for c in children)
    return inner + (max(params) if params else 0)


def environment(df: pd.DataFrame) -> dict[str, pd.Series]:
    close = df["close"].reset_index(drop=True)
    env = {c: df[c].reset_index(drop=True).astype(float) for c in ("open", "high", "low", "close")}
    env["volume"] = df["volume"].reset_index(drop=True).astype(float) if "volume" in df.columns else pd.Series(1.0, index=close.index)
    env["ret"] = close.pct_change()
    env["range"] = (env["high"] - env["low"]) / close
    return env


def evaluate(node: Node, env: dict[str, pd.Series], memo: dict[str, pd.Series] | None = None) -> pd.Series:
    """Value of a tree on the environment of one data set; ``memo`` shares sub-trees between candidates."""
    k = key(node)
    if memo is not None and k in memo:
        return memo[k]
    if node[0] == "col":
        out = env[node[1]]
    else:
        name, params, children = node
        args = [evaluate(c, env, memo) for c in children]
        with np.errstate(all="ignore"):
            if name in WINDOWED:
                out = WINDOWED[name][0](args[0], *params)
            elif name in UNARY:
                out = UNARY[name][0](args[0])
            else:
                out = BINARY[name][0](args[0], args[1])
        out = out.replace([np.inf, -np.inf], np.nan)
    if memo is not None:
        memo[k] = out
    return out


def to_source(node: Node) -> str:
    """The tree as a pandas expression over ``df``."""
    if node[0] == "col":
        return LEAF_SOURCE[node[1]]
    name, params, children = node
    parts = [to_source(c) for c in children]
    if name in WINDOWED:
        return WINDOWED[name][1].format(x=parts[0], n=params[0])
    if name in UNARY:
        return UNARY[name][1].format(x=parts[0])
    return BINARY[name][1].format(a=parts[0], b=parts[1])


def strategy_source(node: Node, rule_window: int, side: str, header: str = "") -> str:
    """A complete ``signal(df)`` file: long when the indicator is above its own moving average (short otherwise)."""
    expr = to_source(node)
    final = "np.where(f > base, 1, -1)" if side == "long_short" else "(f > base).astype(int)"
    return (
        f'{header}"""Indicator found by monte-neo discover: {key(node)}, rule window {rule_window}."""\n\n'
        "import numpy as np\nimport pandas as pd\n\n"
        f"RULE_WINDOW = {rule_window}\n\n\n"
        "def signal(df):\n"
        f"    f = {expr}\n"
        "    base = f.rolling(RULE_WINDOW).mean()\n"
        f"    return pd.Series({final}, index=df.index).where(f.notna() & base.notna(), 0).to_numpy()\n"
    )


def random_tree(rng: np.random.Generator, max_depth: int = 3, columns: tuple[str, ...] = COLUMNS) -> Node:
    """A random causal tree; leaves become likelier as it grows."""
    def grow(level: int) -> Node:
        if level >= max_depth or (level > 0 and rng.random() < 0.3):
            return leaf(str(rng.choice(columns)))
        kind = rng.random()
        if kind < 0.55:
            name = str(rng.choice(sorted(WINDOWED)))
            return op(name, (grow(level + 1),), (int(rng.choice(WINDOWS)),))
        if kind < 0.65:
            return op(str(rng.choice(sorted(UNARY))), (grow(level + 1),))
        a, b = grow(level + 1), grow(level + 1)
        return op(str(rng.choice(sorted(BINARY))), (a, b))

    return grow(0)


def make(rng: np.random.Generator, n: int, max_depth: int = 3, columns: tuple[str, ...] = COLUMNS) -> list[tuple[Node, int]]:
    """Up to ``n`` distinct candidates ``(tree, rule window)``, in a reproducible order."""
    seen: set[str] = set()
    out: list[tuple[Node, int]] = []
    attempts = 0
    while len(out) < n and attempts < 40 * n:
        attempts += 1
        tree, m = random_tree(rng, max_depth, columns), int(rng.choice(RULE_WINDOWS))
        ident = f"{key(tree)}|{m}"
        if tree[0] != "col" and ident not in seen:
            seen.add(ident)
            out.append((tree, m))
    return out


def _positions_in(node: Node) -> list[tuple[int, ...]]:
    """Paths to every node of a tree (the path is the list of child indices)."""
    out: list[tuple[int, ...]] = [()]
    if node[0] != "col":
        for i, child in enumerate(node[2]):
            out += [(i, *p) for p in _positions_in(child)]
    return out


def _at(node: Node, path: tuple[int, ...]) -> Node:
    for i in path:
        node = node[2][i]
    return node


def _replace(node: Node, path: tuple[int, ...], new: Node) -> Node:
    if not path:
        return new
    name, params, children = node[0], node[1], list(node[2])
    children[path[0]] = _replace(children[path[0]], path[1:], new)
    return (name, params, tuple(children))


def mutate(rng: np.random.Generator, node: Node, max_depth: int = 3, columns: tuple[str, ...] = COLUMNS) -> Node:
    """A small causal change of ``node``: a neighbouring window, another column, another operation or a wrapped subtree."""
    path = _positions_in(node)[int(rng.integers(0, len(_positions_in(node))))]
    target = _at(node, path)
    kind = float(rng.random())
    if target[0] == "col":
        new = leaf(str(rng.choice(columns))) if kind < 0.6 else op(str(rng.choice(sorted(WINDOWED))), (target,), (int(rng.choice(WINDOWS)),))
    elif target[0] in WINDOWED:
        if kind < 0.6:
            j = WINDOWS.index(target[1][0]) if target[1][0] in WINDOWS else 0
            j = int(np.clip(j + int(rng.choice((-2, -1, 1, 2))), 0, len(WINDOWS) - 1))
            new = op(target[0], target[2], (WINDOWS[j],))
        elif kind < 0.8:
            new = op(str(rng.choice(sorted(WINDOWED))), target[2], target[1])
        else:
            new = target[2][0]  # drop the operation
    elif target[0] in UNARY:
        new = op(str(rng.choice(sorted(UNARY))), target[2]) if kind < 0.7 else target[2][0]
    else:
        new = op(str(rng.choice(sorted(BINARY))), target[2]) if kind < 0.7 else random_tree(rng, max(1, max_depth - 1), columns)
    out = _replace(node, path, new)
    return out if depth(out) <= max_depth + 1 and out[0] != "col" else node


def describe(node: Node) -> dict[str, Any]:
    return {"key": key(node), "depth": depth(node), "lookback": lookback(node)}


__all__ = ["COLUMNS", "describe", "environment", "evaluate", "key", "leaf", "lookback", "make", "mutate", "op", "random_tree", "strategy_source", "to_source"]
