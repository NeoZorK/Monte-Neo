"""Known-error benchmark of the verifier: generators of well-described backtest mistakes and of honest strategies.

Each case is a generator ``seed -> (data, strategy source, declared trials)`` written from public descriptions of the
mistake, with no code taken from other projects:

* ``next_bar_leak`` - the signal reads the next bar's close (look-ahead; Bailey, Borwein, Lopez de Prado and Zhu 2014,
  "Pseudo-mathematics and financial charlatanism", Notices of the AMS 61(5), discuss the family of backtest errors).
* ``centered_window`` - a centred rolling mean uses bars after ``t``.
* ``global_zscore`` - a z-score with the full-sample mean and standard deviation (information from the future).
* ``selection_bias`` - the best of many random strategies, with the number of trials declared (Harvey and Liu 2015,
  "Backtesting", J. Portfolio Management 42(1); Bailey and Lopez de Prado 2014, the deflated Sharpe ratio).
* ``cost_blind`` - a strategy that trades every bar on a tiny serial correlation and only works without costs.
* ``unadjusted_split`` - a stock split left in the prices (a fake one-bar crash).
* honest controls: ``momentum_ar`` and ``mean_reversion_ar`` (returns with real serial correlation, rules that use only the
  past) must not be rejected; ``noise_strategy`` (random positions, one trial) must not be accepted as ``PASS``.

:func:`run_known_errors` runs every case over many seeds and reports, per case, how often the verifier flagged the
mistake (false negatives are the misses), how often an honest strategy was rejected (false positives) and how often noise
was accepted. The numbers are measured, not promised: a case's expectation is a *rate* on the seeds given.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify import model_from_costs, verify_strategy

FLAG_CHECKS = {
    "next_bar_leak": ("lookahead_truncation", "lookahead_perturbation"),
    "centered_window": ("lookahead_truncation", "lookahead_perturbation"),
    "global_zscore": ("lookahead_truncation", "lookahead_perturbation"),
    "unadjusted_split": ("data_quality",),
}
HEAD = "import numpy as np\nimport pandas as pd\n"


def ar_market(n: int, phi: float, seed: int, *, split_at: int | None = None, sigma: float = 0.004) -> pd.DataFrame:
    """Hourly OHLCV whose returns have serial correlation ``phi`` (0 = random walk); optional unadjusted 2:1 split."""
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    eps = rng.normal(0.0, sigma, n)
    for t in range(1, n):
        r[t] = phi * r[t - 1] + eps[t]
    close = 100.0 * np.exp(np.cumsum(r))
    if split_at is not None:
        close[split_at:] /= 2.0
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.002, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.002, n))
    return pd.DataFrame({
        "timestamp": pd.date_range("2022-01-03", periods=n, freq="h"), "open": open_, "high": high, "low": low,
        "close": close, "volume": rng.uniform(500, 1500, n),
    })


@dataclass(frozen=True)
class Case:
    """One generator: ``kind`` is ``error`` (should be flagged), ``honest`` (must not be rejected) or ``noise`` (must not pass)."""

    id: str
    kind: str
    build: Callable[[int], tuple[pd.DataFrame, str | np.ndarray, int | None]]
    description: str


def _src(body: str) -> str:
    return HEAD + "\ndef signal(df):\n" + "".join(f"    {line}\n" for line in body.strip().splitlines())


def _case_next_bar_leak(seed: int) -> tuple[pd.DataFrame, str, int | None]:
    return ar_market(1500, 0.0, seed), _src('return (df["close"].shift(-1) > df["close"]).astype(int).to_numpy()'), None


def _case_centered_window(seed: int) -> tuple[pd.DataFrame, str, int | None]:
    return ar_market(1500, 0.0, seed), _src('m = df["close"].rolling(21, center=True).mean()\nreturn (df["close"] > m).fillna(False).astype(int).to_numpy()'), None


def _case_global_zscore(seed: int) -> tuple[pd.DataFrame, str, int | None]:
    return ar_market(1500, 0.0, seed), _src('z = (df["close"] - df["close"].mean()) / df["close"].std()\nreturn np.sign(-z).fillna(0).to_numpy()'), None


def _case_selection_bias(seed: int) -> tuple[pd.DataFrame, np.ndarray, int | None]:
    df = ar_market(1500, 0.0, seed)
    rng = np.random.default_rng(seed + 1000)
    ret = df["close"].pct_change().fillna(0).to_numpy()
    best, best_pos = -np.inf, None
    for _ in range(300):  # the "researcher" tries 300 random rules and keeps the best
        pos = np.sign(rng.normal(size=len(df)))
        pos = np.r_[0.0, pos[:-1]]
        pnl = float((pos * ret).sum())
        if pnl > best:
            best, best_pos = pnl, pos
    return df, np.asarray(best_pos, dtype=np.int64), 300  # positions only: the verifier sees a signals file, no code


def _case_cost_blind(seed: int) -> tuple[pd.DataFrame, str, int | None]:
    return ar_market(3000, 0.05, seed), _src('r = df["close"].pct_change().fillna(0)\nreturn np.sign(r).to_numpy()'), None


def _case_unadjusted_split(seed: int) -> tuple[pd.DataFrame, str, int | None]:
    df = ar_market(1500, 0.0, seed, split_at=900)
    return df, _src('return np.where(df["close"].pct_change().fillna(0) < -0.3, -1, 1)'), None  # shorts the "crash"


def _case_momentum_ar(seed: int) -> tuple[pd.DataFrame, str, int | None]:
    return ar_market(3000, 0.2, seed, sigma=0.01), _src('return np.sign(df["close"].pct_change().fillna(0)).to_numpy()'), None


def _case_mean_reversion_ar(seed: int) -> tuple[pd.DataFrame, str, int | None]:
    return ar_market(3000, -0.2, seed, sigma=0.01), _src('return -np.sign(df["close"].pct_change().fillna(0)).to_numpy()'), None


def _case_noise(seed: int) -> tuple[pd.DataFrame, np.ndarray, int | None]:
    rng = np.random.default_rng(seed + 7)
    return ar_market(1500, 0.0, seed), np.sign(rng.normal(size=1500)).astype(np.int64), 1


CASES: tuple[Case, ...] = (
    Case("next_bar_leak", "error", _case_next_bar_leak, "signal reads the next bar's close"),
    Case("centered_window", "error", _case_centered_window, "centred rolling mean"),
    Case("global_zscore", "error", _case_global_zscore, "z-score with full-sample mean and std"),
    Case("selection_bias", "error", _case_selection_bias, "best of 300 random rules, trials declared"),
    Case("cost_blind", "error", _case_cost_blind, "trades every bar on a tiny serial correlation"),
    Case("unadjusted_split", "error", _case_unadjusted_split, "a 2:1 split left in the prices"),
    Case("momentum_ar", "honest", _case_momentum_ar, "rule on past returns, returns are serially correlated"),
    Case("mean_reversion_ar", "honest", _case_mean_reversion_ar, "contrarian rule, returns mean-revert"),
    Case("noise_strategy", "noise", _case_noise, "random positions, one declared trial"),
)


def run_case(case: Case, seed: int, *, commission_bps: float = 5.0, slippage_bps: float = 5.0) -> dict[str, Any]:
    """Verify one seed of one case; returns the verdict, what flagged it and whether the verifier behaved as expected."""
    df, payload, trials = case.build(seed)
    model = model_from_costs(commission_bps=commission_bps, slippage_bps=slippage_bps, n_bars=len(df))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if isinstance(payload, str):
            scope: dict[str, Any] = {"__name__": "known_error"}
            exec(compile(payload, "<known_error>", "exec"), scope)  # noqa: S102 - generated above, no outside input
            rep = verify_strategy(df, signal_fn=scope["signal"], source=payload, n_trials=trials, model=model)
        else:
            rep = verify_strategy(df, signals=payload, n_trials=trials, model=model)
    status = {c["id"]: c["status"] for c in rep["checks"]}
    flagged_by = [i for i in FLAG_CHECKS.get(case.id, ()) if status.get(i) in ("fail", "warn")]
    verdict = rep["verdict"]
    if case.kind == "error":
        ok = bool(flagged_by) if case.id in FLAG_CHECKS else verdict != "PASS"  # statistical errors: any non-PASS verdict
    elif case.kind == "honest":
        ok = verdict != "REJECT"
    else:
        ok = verdict != "PASS"
    return {"verdict": verdict, "flagged_by": flagged_by, "ok": ok}


def run_known_errors(seeds: int = 10, cases: tuple[Case, ...] = CASES) -> dict[str, Any]:
    """Run every case over ``seeds`` seeds; ``miss_rate`` (errors), ``false_reject_rate`` (honest), ``false_accept_rate`` (noise)."""
    out: dict[str, Any] = {"seeds": int(seeds), "cases": {}}
    for case in cases:
        runs = [run_case(case, s) for s in range(int(seeds))]
        bad = 1.0 - sum(r["ok"] for r in runs) / len(runs)
        key = {"error": "miss_rate", "honest": "false_reject_rate", "noise": "false_accept_rate"}[case.kind]
        verdicts: dict[str, int] = {}
        for r in runs:
            verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
        out["cases"][case.id] = {"kind": case.kind, "description": case.description, key: bad, "verdicts": verdicts}
    return out


def render_markdown(report: dict[str, Any]) -> str:
    """The report as a table for the documentation."""
    lines = [f"Known-error benchmark, {report['seeds']} seeds per case.", "", "| Case | Kind | Bad outcome rate | Verdicts |", "|---|---|---|---|"]
    for cid, c in report["cases"].items():
        rate = next(c[k] for k in ("miss_rate", "false_reject_rate", "false_accept_rate") if k in c)
        lines.append(f"| {cid} | {c['kind']} | {rate:.0%} | {', '.join(f'{k} {v}' for k, v in sorted(c['verdicts'].items()))} |")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - documentation run: python -m monte_neo.bench.known_errors [seeds]
    import sys

    print(render_markdown(run_known_errors(int(sys.argv[1]) if len(sys.argv) > 1 else 10)))
