"""A hold-out oracle for agents (Thresholdout).

An agent that asks "does this variant work on the test set?" two hundred times is fitting the test set, one
yes or no at a time. The oracle keeps the last part of the data apart and answers like Thresholdout
(Dwork et al., 2015): when the training and hold-out results agree within a tolerance it returns the *training*
number, which tells nothing new about the hold-out; only when they disagree does it return a noisy hold-out
number, and every such answer spends one unit of a budget. When the budget is gone, the hold-out is used up.

The state is a hash-chained file, so queries cannot be removed. The oracle protects against accidental
over-fitting by many queries; it does not hide the file from a process that can read the disk (run the MCP
server where the agent cannot read ``.monte-neo``).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.chainlog import ChainLog
from monte_neo.verify.ledger import variant_id
from monte_neo.verify.returns import annualized_sharpe, strategy_returns

DEFAULT_PATH = Path(".monte-neo") / "oracle.jsonl"


def _data_id(df: pd.DataFrame) -> str:
    cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
    return hashlib.sha256(np.ascontiguousarray(df[cols].to_numpy(dtype=np.float64)).tobytes()).hexdigest()[:16]


class HoldoutOracle:
    def __init__(self, path: str | Path | None = None) -> None:
        self.log = ChainLog(path or DEFAULT_PATH)

    def init(self, df: pd.DataFrame, *, holdout: float = 0.2, budget: int = 10, threshold: float = 0.5, sigma: float = 0.2, seed: int = 1) -> dict[str, Any]:
        if self.log.entries():
            raise ValueError(f"{self.log.path} already exists: an oracle is initialised once per data set")
        if not 0.05 <= holdout <= 0.5:
            raise ValueError(f"holdout must be between 0.05 and 0.5, got {holdout}")
        if budget < 1 or threshold <= 0 or sigma < 0:
            raise ValueError("budget must be >= 1, threshold > 0 and sigma >= 0")
        return self.log.append({"kind": "init", "data": _data_id(df), "bars": len(df), "holdout": holdout, "budget": budget, "threshold": threshold, "sigma": sigma, "seed": seed})

    def _state(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        chain = self.log.check()
        if not chain["ok"]:
            raise ValueError(f"the oracle file was changed: {chain['problem']}")
        entries = self.log.entries()
        if not entries or entries[0].get("kind") != "init":
            raise ValueError("the oracle is not initialised: run `monte-neo oracle init` first")
        return entries[0], entries[1:]

    def status(self) -> dict[str, Any]:
        init, queries = self._state()
        spent = sum(1 for q in queries if q.get("spent"))
        return {"queries": len(queries), "budget": init["budget"], "budget_left": init["budget"] - spent, "holdout": init["holdout"], "data": init["data"]}

    def query(self, df: pd.DataFrame, strategy: Any, *, source: str | None = None) -> dict[str, Any]:
        """Ask whether ``strategy``'s hold-out result is consistent with its training result."""
        init, queries = self._state()
        if _data_id(df) != init["data"] or len(df) != init["bars"]:
            raise ValueError("this is not the data the oracle was initialised on")
        rets, ppy, src = strategy_returns(df, strategy)
        variant = variant_id(source or src)
        for q in queries:
            if variant is not None and q.get("variant") == variant:
                return {**q["answer"], "repeated": True, "budget_left": self.status()["budget_left"]}
        left = self.status()["budget_left"]
        if left <= 0:
            raise ValueError("the hold-out is used up: every unit of budget was spent on a disagreement; collect new data")
        cut = int(rets.size * (1.0 - init["holdout"]))
        train, hold = annualized_sharpe(rets[:cut], ppy), annualized_sharpe(rets[cut:], ppy)
        rng = np.random.default_rng(int(hashlib.sha256(f"{init['seed']}:{len(queries)}".encode()).hexdigest()[:8], 16))
        noisy = abs(train - hold) > init["threshold"] + rng.laplace(0.0, 2.0 * init["sigma"])
        if noisy:
            answer = {"consistent": False, "value": round(float(hold + rng.laplace(0.0, init["sigma"])), 3), "kind": "noisy hold-out Sharpe"}
        else:
            answer = {"consistent": True, "value": round(float(train), 3), "kind": "training Sharpe (the hold-out agrees within the tolerance)"}
        self.log.append({"kind": "query", "variant": variant, "spent": bool(noisy), "answer": answer})
        return {**answer, "repeated": False, "budget_left": left - int(noisy)}


__all__ = ["DEFAULT_PATH", "HoldoutOracle"]
