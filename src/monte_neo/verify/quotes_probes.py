"""The look-ahead probes of ``verify_strategy``, run on the bars a strategy reads in a quote run.

``arrival_lookahead`` asks whether the profit survives the *time* data arrived. It cannot see a strategy that reads the
*future* of its own bars (``shift(-1)``): that leak exists on every clock. The truncation and perturbation probes, the static
lint and the other look-ahead checks of :func:`monte_neo.verify.verify_strategy` find it, so a quote run reuses them on the
arrival-clock bars (every feed, with the alias prefixes the strategy reads).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.ingest import SignalFn
from monte_neo.verify.verdict import verify_strategy


def lookahead_rows(
    info: dict[str, np.ndarray], fn: SignalFn, source: str | None, model: ExecutionModel, positions: str
) -> list[dict[str, Any]]:
    """The ``lookahead`` check rows of a normal verification of the strategy on ``info`` (the bars it reads)."""
    report = verify_strategy(pd.DataFrame(dict(info)), signal_fn=fn, source=source, model=model, n_trials=1, positions=positions)
    return [c for c in report["checks"] if c["category"] == "lookahead"]


__all__ = ["lookahead_rows"]
