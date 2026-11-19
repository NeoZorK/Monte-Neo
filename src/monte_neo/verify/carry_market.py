"""Market adapters for delta-neutral carry: the verifier's accuracy, sample-size and benchmark rules, read from the economics of carry.

Why carry needs its own rules (derived from what the position earns, not from any one result):

* **Accuracy.** A hedged pair accrues funding almost every bar it is held, and funding is positive most of the time, so "the share of
  profitable bars" is high by construction and says nothing about leakage. The directional part of the P&L is the *basis* (spot
  minus perpetual); the hit rate is therefore measured on the basis index. A rule that peeks at the next basis move still gets a
  near-perfect hit rate there and fails. Leakage of future *funding* is probed separately (``carry_future_probe``).
* **Sample.** Trades are rare (a few entries a year) but the evidence of carry is the accrual over many bars, which are strongly
  autocorrelated. The sample is the *effective number of independent accrual periods*, ``n_held * gamma0 / LRV`` from the
  Newey-West long-run variance of the returns while held, capped at ``n_held``; closed trades are reported next to it and the
  small number of entry and exit decisions is a separate warning.
* **Benchmark.** The market a carry book must be independent of is the underlying (spot), not the hedged pair itself.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check
from monte_neo.verify.lookahead import implausible_accuracy
from monte_neo.verify.market import SingleMarket, UniverseMarket

CARRY_COLUMNS = ("spot_close", "perp_close", "funding_rate", "basis_pnl")
MIN_HELD_BARS = 30


def is_carry(df: pd.DataFrame) -> bool:
    return all(c in df.columns for c in CARRY_COLUMNS)


def effective_sample(returns: np.ndarray) -> dict[str, float]:
    """``{n, n_eff, ratio}``: bars held and the effective number of independent periods (Newey-West long-run variance)."""
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 3:
        return {"n": float(n), "n_eff": float(n), "ratio": 1.0}
    d = x - x.mean()
    g0 = float(d @ d) / n
    if g0 <= 0:
        return {"n": float(n), "n_eff": float(n), "ratio": 1.0}
    lag = min(max(1, int(4 * (n / 100.0) ** (2 / 9))), n - 2)
    # a longer window than the usual rule: accrual is smooth, and a short window understates the long-run variance
    lag = min(max(lag, int(n ** (1 / 3)) * 2), n - 2)
    lrv = g0
    for k in range(1, lag + 1):
        lrv += 2.0 * (1.0 - k / (lag + 1.0)) * float(d[k:] @ d[:-k]) / n
    ratio = min(1.0, g0 / lrv) if lrv > 0 else 1.0 / n
    return {"n": float(n), "n_eff": float(max(1.0, n * ratio)), "ratio": float(ratio)}


def sample_row(rets: np.ndarray, held: np.ndarray, n_closed: int, min_effective: int) -> dict[str, Any]:
    """Row ``sample_size`` for carry: effective independent accrual periods while held, with the closed trades beside it."""
    n = min(rets.size, held.size)
    sel = np.asarray(rets[-n:], dtype=float)[np.asarray(held[-n:], dtype=bool)]
    es = effective_sample(sel)
    ok = es["n"] >= MIN_HELD_BARS and es["n_eff"] >= min_effective
    summary = (f"{es['n_eff']:.0f} effective independent accrual periods ({es['n']:.0f} held bars, autocorrelation ratio {es['ratio']:.2f}; "
               f"min {min_effective}); {n_closed} closed trades")
    return check("sample_size", "statistics", "pass" if ok else "fail", summary,
                 {"n_closed_trades": n_closed, "held_bars": es["n"], "effective_n": es["n_eff"], "autocorrelation_ratio": es["ratio"],
                  "min_effective": min_effective, "basis": "effective independent accrual periods (Newey-West), not closed trades"})


def few_decisions_row(n_entries: int, years: float) -> dict[str, Any]:
    """Row ``few_decisions``: the entry and exit rule was tested on very few decisions; a warning, never a substitute for the sample."""
    per_year = n_entries / years if years > 0 else 0.0
    if n_entries < 10:
        return check("few_decisions", "statistics", "warn",
                     f"only {n_entries} entry decisions ({per_year:.1f} a year): the rule that decides when to hold the pair is hardly tested; "
                     "the accrual sample above says nothing about it", {"entries": n_entries, "per_year": per_year})
    return check("few_decisions", "statistics", "pass", f"{n_entries} entry decisions ({per_year:.1f} a year)", {"entries": n_entries, "per_year": per_year})


def carry_independence(frame: pd.DataFrame, fn: Any, full: np.ndarray, mode: str) -> dict[str, Any]:
    """Do the positions react to unrelated carry inputs? A carry rule reads funding and basis, not the hedged index.

    The prices and the funding (of every coin, for a basket) are replaced by their time-reversed copies and the table is rebuilt, so
    the basis follows; a rule that answers the same holds a stored answer.
    """
    from monte_neo.verify.carry import carry_table
    from monte_neo.verify.lookahead import SAME_SHARE, run_positions

    changes = int(np.count_nonzero(np.diff(full) != 0)) if full.size > 1 else 0
    if changes < 4:
        return {"status": "skip", "reason": "positions (almost) never change", "position_changes": changes}
    keep = ["timestamp", "spot_close", "perp_close", "funding_rate"] + [c for c in ("symbol", "in_universe") if c in frame.columns]
    raw = frame[keep].copy()
    for c in ("spot_close", "perp_close", "funding_rate"):
        raw[c] = raw.groupby("symbol")[c].transform(lambda x: x.to_numpy()[::-1]) if "symbol" in raw.columns else raw[c].to_numpy()[::-1]
    try:
        other = run_positions(fn, frame, [carry_table(raw)], mode)[0]
    except Exception as exc:
        return {"status": "skip", "reason": f"the strategy failed on the foreign table: {type(exc).__name__}"}
    same = float(np.mean(other == full))
    stored = same >= SAME_SHARE
    return {"status": "warn" if stored else "pass", "kind": "ignores prices and dates" if stored else "reads the prices", "same_on_foreign_prices": same,
            "same_on_foreign_prices_and_dates": None, "position_changes": changes, "stored_answer": bool(stored)}


def _basis_index(basis_pnl: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Open and close of the cumulative basis index, shape of ``basis_pnl`` (bars[, symbols])."""
    close = 100.0 * np.cumprod(1.0 + np.nan_to_num(basis_pnl), axis=0)
    open_ = np.concatenate([np.full((1, *close.shape[1:]), 100.0), close[:-1]], axis=0)
    return open_, close


class CarryMarket(SingleMarket):
    """One hedged pair."""

    carry = True
    benchmark_description = "hold the hedged pair every bar, same costs"

    def __init__(self, df: pd.DataFrame) -> None:
        super().__init__(df)
        self.spot = df["spot_close"].to_numpy(dtype=np.float64)

    def parts(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        f = self.frame
        return tuple(f[c].to_numpy(dtype=np.float64).reshape(-1, 1) for c in ("funding_rate", "basis_pnl", "perp_close"))  # type: ignore[return-value]

    def perp_high(self) -> np.ndarray | None:
        return self.frame["perp_high"].to_numpy(dtype=np.float64).reshape(-1, 1) if "perp_high" in self.frame.columns else None

    def accuracy(self, traded: np.ndarray) -> dict[str, Any]:
        o, c = _basis_index(self.frame["basis_pnl"].to_numpy(dtype=np.float64))
        return {**implausible_accuracy(o, c, traded), "measured_on": "basis (the directional part of carry)"}

    def independence(self, fn: Any, full: np.ndarray, mode: str) -> dict[str, Any] | None:
        return carry_independence(self.frame, fn, full, mode)

    def reference_returns(self, warmup: int) -> np.ndarray:
        s = self.spot[warmup:]
        return s[1:] / s[:-1] - 1.0 if s.size > 1 else np.zeros(0)

    def held(self, sig: np.ndarray, warmup: int, n_rets: int) -> np.ndarray:
        return np.asarray(sig, dtype=float)[warmup:warmup + n_rets] > 0

    def market_close(self) -> np.ndarray:
        return self.spot

    def data_bytes(self) -> bytes:
        extra = self.frame[["spot_close", "perp_close", "funding_rate"]].to_numpy(dtype=np.float64)
        return super().data_bytes() + np.ascontiguousarray(extra).tobytes()


class CarryUniverse(UniverseMarket):
    """A basket of hedged pairs, one row per timestamp and coin."""

    carry = True
    benchmark_description = "equal weight in every hedged pair, same costs"

    def __init__(self, df: pd.DataFrame) -> None:
        super().__init__(df)
        shape = (self.n_bars, len(self.symbols))
        self._m: dict[str, np.ndarray] = {}
        for col in ("spot_close", "perp_close", "funding_rate", "basis_pnl", "perp_high", "in_universe"):
            if col not in self.frame.columns:
                continue
            m = np.full(shape, np.nan)
            m[self.t_idx, self.s_idx] = pd.to_numeric(self.frame[col], errors="coerce").to_numpy(dtype=np.float64)
            self._m[col] = m

    def parts(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return self._m["funding_rate"], self._m["basis_pnl"], self._m["perp_close"]

    def perp_high(self) -> np.ndarray | None:
        return self._m.get("perp_high")

    def independence(self, fn: Any, full: np.ndarray, mode: str) -> dict[str, Any] | None:
        return carry_independence(self.frame, fn, full, mode)

    def member_matrix(self) -> np.ndarray | None:
        return self._m.get("in_universe")

    def universe_checks(self) -> list[dict[str, Any]]:
        """Survivorship for a basket: a hand-made list of coins does not lift the cap; an ex-ante rule the verifier recomputed can."""
        row = dict(super().universe_checks()[0])
        det = {**row.get("details", {}), "exante_rule_required": True}
        rule = "in_universe" in self.frame.columns
        if row["status"] == "skip":
            return [row]
        if rule and det.get("stopped_count", 0) == 0:
            row = check("survivorship", "integrity", "warn", "the composition follows an ex-ante rule the verifier recomputed, but no coin of the pool stops trading inside the sample: "
                        "coins that were large and then vanished are not in it, so the cap stays", det)
        elif rule:
            row = check("survivorship", "integrity", "pass", "the composition follows an ex-ante rule the verifier recomputed on each date from earlier data, and coins of the pool "
                        "stop trading inside the sample", det)
        elif row["status"] == "warn":
            row = check("survivorship", "integrity", "warn", "no ex-ante composition rule: a hand-made list of coins keeps the cap (declare the rule: universe_rule=top N by perpetual volume over the past days)", det)
        return [row]

    def accuracy(self, traded: np.ndarray) -> dict[str, Any]:
        o, c = _basis_index(self._m["basis_pnl"])
        return {**implausible_accuracy(o, c, traded), "measured_on": "basis (the directional part of carry)"}

    def reference_returns(self, warmup: int) -> np.ndarray:
        s = self._m["spot_close"][warmup:]
        with np.errstate(divide="ignore", invalid="ignore"):
            step = s[1:] / s[:-1] - 1.0
        return np.nan_to_num(np.nanmean(np.where(np.isfinite(step), step, np.nan), axis=1)) if s.shape[0] > 1 else np.zeros(0)

    def held(self, sig: np.ndarray, warmup: int, n_rets: int) -> np.ndarray:
        return (np.abs(np.asarray(sig, dtype=float)).sum(axis=1)[warmup:warmup + n_rets]) > 0

    def market_close(self) -> np.ndarray:
        s = self._m["spot_close"]
        with np.errstate(divide="ignore", invalid="ignore"):
            step = np.nanmean(np.where(np.isfinite(s[1:] / s[:-1]), s[1:] / s[:-1] - 1.0, np.nan), axis=1)
        return np.concatenate([[1.0], np.cumprod(1.0 + np.nan_to_num(step))])

    def data_bytes(self) -> bytes:
        extra = np.concatenate([np.nan_to_num(self._m[c]).ravel() for c in ("spot_close", "perp_close", "funding_rate")])
        return super().data_bytes() + np.ascontiguousarray(extra).tobytes()


def simulate_margin(w: np.ndarray, perp: np.ndarray, high: np.ndarray | None, funding: np.ndarray | None, leverage: float, maintenance: float,
                    policy: dict[str, float] | None) -> dict[str, Any]:
    """Margin account of the short perpetual, per held episode and coin (per unit of perpetual notional at entry).

    Equity is ``initial margin + funding received - (price / entry - 1)`` plus transfers that arrived; the position is liquidated on
    a bar when the equity at the bar's **high** (the worst price of the bar for a short, not the close) is at or below the maintenance
    margin of the notional at that price. With a ``policy`` the account is looked at on every close: when equity is below ``trigger`` of
    the notional a transfer back to ``1/leverage`` is ordered, it arrives ``delay_bars`` bars later (the bar can liquidate in
    between) and costs ``cost_bps`` of the amount moved. Without a policy nothing is ever added.
    """
    wa = np.abs(np.nan_to_num(w))
    wa = wa.reshape(-1, 1) if wa.ndim == 1 else wa
    pc = perp.reshape(-1, 1) if perp.ndim == 1 else perp
    ph = pc if high is None else (high.reshape(-1, 1) if high.ndim == 1 else np.fmax(high, pc))
    fd = np.zeros_like(pc) if funding is None else np.nan_to_num(funding.reshape(-1, 1) if funding.ndim == 1 else funding)
    init = 1.0 / leverage
    prev = np.vstack([np.zeros((1, wa.shape[1])), wa[:-1]]) > 0  # held over bar t, decided at t-1
    pol = policy or {}
    trigger, delay, cost = float(pol.get("trigger", 0.0)), int(pol.get("delay_bars", 0)), float(pol.get("cost_bps", 0.0)) / 1e4
    episodes = liquidated = late = topups = 0
    moved = paid = worst_rise = 0.0
    min_ratio = float("inf")
    first_at: int | None = None
    for j in range(wa.shape[1]):
        live, dead, pending = False, False, []  # pending: (arrival bar, amount)
        p0 = margin = cumf = 0.0
        for t in range(1, wa.shape[0]):
            if not prev[t, j]:
                live = dead = False
                pending = []
                continue
            if not live and not dead:
                live, p0, margin, cumf, pending = True, pc[t - 1, j], init, 0.0, []
                episodes += 1
            if not (np.isfinite(p0) and p0 > 0 and np.isfinite(pc[t, j])):
                continue
            if dead:  # liquidated: the episode goes on in the data, only its worst rise is still recorded
                worst_rise = max(worst_rise, (ph[t, j] if np.isfinite(ph[t, j]) else pc[t, j]) / p0 - 1.0)
                continue
            for arr, amt in [x for x in pending if x[0] <= t]:
                margin += amt
            pending = [x for x in pending if x[0] > t]
            hi = ph[t, j] if np.isfinite(ph[t, j]) else pc[t, j]
            worst_rise = max(worst_rise, hi / p0 - 1.0)
            eq_hi = margin + cumf - (hi / p0 - 1.0)
            if eq_hi <= maintenance * (hi / p0):
                liquidated += 1
                late += int(bool(pending))
                first_at = t if first_at is None else first_at
                live, dead = False, True
                continue
            cumf += fd[t, j] * (pc[t, j] / p0)
            eq = margin + cumf - (pc[t, j] / p0 - 1.0)
            ratio = eq / (pc[t, j] / p0)
            min_ratio = min(min_ratio, ratio)
            if policy and ratio < trigger and not pending:
                amt = init * (pc[t, j] / p0) - eq
                pending.append((t + 1 + delay, amt))
                topups += 1
                moved += amt
                paid += amt * cost
    return {"episodes": episodes, "liquidated_episodes": liquidated, "first_liquidation_bar": first_at, "topups": topups, "topup_total_share": moved,
            "transfer_cost_share": paid, "liquidated_with_transfer_pending": late, "worst_rise_while_held": worst_rise, "min_margin_ratio": None if min_ratio == float("inf") else min_ratio,
            "intrabar": high is not None}


def margin_rows(weights: np.ndarray, perp: np.ndarray, leverage: float, maintenance: float = 0.005, *, perp_high: np.ndarray | None = None,
                funding: np.ndarray | None = None, policy: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Rows ``carry_margin`` (under the declared collateral policy, or with no top-ups when none is declared) and, when a policy
    is declared, ``carry_margin_no_topup`` (information: what happens with no collateral management at all).

    The hedge does not help the margin account: the spot leg is not collateral for the perpetual. Liquidation is tested on the bar's
    high when ``perp_high`` is given; on the close only otherwise, which understates the risk and is said so. A policy is a dict:
    ``trigger`` (top up when equity is below this share of the notional), ``delay_bars`` (bars until the transfer arrives) and
    ``cost_bps`` (cost of moving or selling, on the amount moved).

    Raises:
        ValueError: Leverage below 1, a maintenance margin outside [0, 1), or a policy trigger outside (0, 1/leverage].
    """
    if leverage < 1.0 or not 0.0 <= maintenance < 1.0:
        raise ValueError("leverage must be >= 1 and the maintenance margin in [0, 1)")
    if policy is not None and not 0.0 < float(policy.get("trigger", 0.0)) <= 1.0 / leverage:
        raise ValueError("policy trigger must be in (0, 1/leverage]: the share of the notional below which collateral is added")
    buffer = 1.0 / leverage - maintenance
    run = simulate_margin(weights, perp, perp_high, funding, leverage, maintenance, policy)
    none = run if policy is None else simulate_margin(weights, perp, perp_high, funding, leverage, maintenance, None)
    base = {"leverage": leverage, "maintenance_margin": maintenance, "margin_buffer": buffer, "policy": policy, **run,
            "topup_needed_share_of_perp_notional": max(0.0, run["worst_rise_while_held"] - buffer)}
    note = "" if run["intrabar"] else "; bar highs were not given, so liquidation was tested on closes only, which understates the risk"
    if run["liquidated_episodes"]:
        how = f"{run['liquidated_episodes']} of {run['episodes']} episodes liquidated"
        why = ("even with the declared top-ups: the transfer did not arrive in time or was too small" if policy and run["topups"] else
               ("with the declared policy" if policy else "with no collateral management"))
        main = check("carry_margin", "economics", "fail", f"{how} at {leverage:g}x ({why}); the perpetual rose up to {run['worst_rise_while_held']:.0%} above its entry, buffer {buffer:.0%}{note}", base)
    elif policy and run["topups"]:
        main = check("carry_margin", "economics", "warn", f"survives only by adding {run['topup_total_share']:.0%} of the perpetual notional in {run['topups']} transfers "
                     f"(cost {run['transfer_cost_share']:.2%}); that cash must be held in reserve{note}", base)
    elif not policy and run["worst_rise_while_held"] >= 0.6 * buffer:
        main = check("carry_margin", "economics", "warn", f"the perpetual rose {run['worst_rise_while_held']:.0%} above its entry while held; the buffer at {leverage:g}x is {buffer:.0%}{note}", base)
    elif not run["intrabar"]:
        main = check("carry_margin", "economics", "warn", f"no liquidation on closes at {leverage:g}x, buffer {buffer:.0%}{note}", base)
    else:
        main = check("carry_margin", "economics", "pass", f"worst rise while held {run['worst_rise_while_held']:.0%}, buffer at {leverage:g}x is {buffer:.0%}, no liquidation on bar highs", base)
    if run["episodes"] == 0:
        main = check("carry_margin", "economics", "skip", "the strategy never held the pair: no margin account to test", base)
    out = [main]
    if policy is not None:
        out.append(check("carry_margin_no_topup", "economics", "info",
                         f"with no collateral management: {none['liquidated_episodes']} of {none['episodes']} episodes liquidated at {leverage:g}x "
                         f"(worst rise {none['worst_rise_while_held']:.0%})", {**none, "leverage": leverage}))
    return out


def entries(weights: np.ndarray) -> int:
    """Number of times a position is opened (per symbol)."""
    w = np.abs(np.nan_to_num(weights))
    w = w.reshape(-1, 1) if w.ndim == 1 else w
    on = w > 0
    return int(np.sum(on[1:] & ~on[:-1]) + np.sum(on[0]))


__all__ = ["CarryMarket", "CarryUniverse", "effective_sample", "entries", "few_decisions_row", "is_carry", "margin_rows", "sample_row", "simulate_margin"]
