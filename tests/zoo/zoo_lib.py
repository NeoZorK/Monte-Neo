"""Hypothesis zoo: strategies built from (mechanism, disguise) with a known answer.

A mechanism is a feature expression over ``df`` plus a rule that turns it into positions. The label
"leaks" is part of the table and is checked by an independent oracle that does not use the verifier:
the positions at bars <= t must not change when the bars after t are removed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.backtest import synthetic_ohlcv

RULES = {
    "R1": 'np.sign(x - df["close"])',
    "R2": "-np.sign(x)",
    "R3": "np.sign(x.diff())",
    "R5": "np.sign(x)",
    "R8": "np.sign(0.5 - x)",
    "R9": "np.sign(2 - x)",
    "R10": "np.sign(x - 0.5)",
    "R11": "np.sign(5 - x)",
}
PRELUDE = "import numpy as np\nimport pandas as pd\nimport scipy.signal\nimport scipy.ndimage\nimport scipy.stats\nimport scipy.interpolate\n"
DISGUISES = ("direct", "helper", "lambda", "pipe", "method", "dynamic")


def dataset(n: int = 1200, seed: int = 1) -> pd.DataFrame:
    """Hourly bars of a random walk with volume."""
    df = synthetic_ohlcv(n, seed=seed)
    df["timestamp"] = pd.date_range("2022-01-03", periods=len(df), freq="h")
    return df


def build(expr: str, rule: str, disguise: str, pre: tuple[str, ...] = ()) -> str:
    """Python source of ``signal(df)`` that computes the same feature in the given disguise."""
    rule_expr = RULES[rule]
    lines = "".join(f"    {line}\n" for line in pre)
    finish = f"    return pd.Series({rule_expr}, index=df.index).fillna(0).to_numpy()\n"
    head = PRELUDE
    if disguise == "direct":
        body = f"def signal(df):\n{lines}    x = {expr}\n{finish}"
    elif disguise == "helper":
        body = f"def _feature(df):\n{lines}    return {expr}\n\n\ndef signal(df):\n    x = _feature(df)\n{finish}"
    elif disguise == "lambda":
        if pre:
            return build(expr, rule, "helper", pre)  # a lambda cannot hold statements
        body = f"_feature = lambda df: {expr}\n\n\ndef signal(df):\n    x = _feature(df)\n{finish}"
    elif disguise == "pipe":
        body = f"def _feature(df):\n{lines}    return {expr}\n\n\ndef signal(df):\n    x = df.pipe(_feature)\n{finish}"
    elif disguise == "method":
        pre8 = "".join(f"        {line}\n" for line in pre)
        finish8 = f"        return pd.Series({rule_expr}, index=df.index).fillna(0).to_numpy()\n"
        body = (
            f"class Strategy:\n    def feature(self, df):\n{pre8}        return {expr}\n\n"
            f"    def signal(self, df):\n        x = self.feature(df)\n{finish8}\n\n"
            "def signal(df):\n    return Strategy().signal(df)\n"
        )
    elif disguise == "dynamic":
        src = repr("\n".join(pre + (f"__x = {expr}",))) if pre else repr(f"__x = {expr}")
        body = (
            f"_CODE = {src}\n\n\ndef signal(df):\n    scope = {{'np': np, 'pd': pd, 'scipy': scipy, 'df': df}}\n"
            "    exec(_CODE, scope)\n    x = scope['__x']\n" + finish
        )
    else:
        raise ValueError(disguise)
    return head + "\n" + body


def compile_signal(source: str):  # noqa: ANN201
    scope: dict = {"__name__": "zoo_strategy"}
    exec(compile(source, "<zoo>", "exec"), scope)  # noqa: S102 - generated from the tables in this package
    return scope["signal"]


def oracle_causal(expr: str, rule: str, pre: tuple[str, ...], df: pd.DataFrame) -> bool:
    """True when positions at bars <= t never change if the bars after t are removed (independent of the verifier)."""
    fn = compile_signal(build(expr, rule, "direct", pre))
    full = np.asarray(fn(df.copy()), dtype=float)
    for t in (151, 233, 307, 419, 523, 607, 701, 773, 859, 911, 997, 1087):
        head = np.asarray(fn(df.iloc[: t + 1].reset_index(drop=True).copy()), dtype=float)
        if not np.array_equal(head, full[: t + 1]):
            return False
    return True
