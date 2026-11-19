"""Cost profiles and cost gates: exchange fee tiers, spread from real quotes, and doubled-cost sensitivity.

* **Fee tiers** are named (maker, taker) schedules in bps per side. The values are *reference figures for orientation*
  (Binance public fee pages, retail tiers); exchanges change them, so check the live schedule and pass your own
  ``(maker, taker)`` pair when it differs. ``maker_share`` is the fraction of fills that rest as maker orders; the default
  is 0 (every fill pays taker), the conservative choice.
* **Spread from quotes**: the median half-spread ``(ask - bid) / (ask + bid)`` of real quotes replaces the Corwin-Schultz
  high-low estimate (Corwin and Schultz 2012), which is noisy and biased up in volatile bars. Crossed quotes are dropped.
* **Cost realism** re-runs the strategy with fee + half-spread per side. A strategy that is profitable at the modeled cost
  but not at the realistic one is an optimistic backtest: a ``fail`` when the spread comes from quotes, a ``warn`` when it
  is only the high-low estimate.
* **Cost sensitivity** doubles the costs (the standard "would it survive if my cost estimate is half of reality" test).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.checks import check
from monte_neo.verify.engine import total_return as _total_return

# (maker_bps, taker_bps) per side. Orientation only: verify against the exchange's current schedule.
FEE_PROFILES: dict[str, tuple[float, float]] = {
    "binance_spot": (10.0, 10.0),
    "binance_spot_bnb": (7.5, 7.5),
    "binance_usdm": (2.0, 5.0),
    "binance_usdm_vip1": (1.6, 4.0),
    "binance_usdm_vip2": (1.4, 3.5),
    "binance_usdm_vip3": (1.2, 3.2),
}
MIN_QUOTES = 50
MULTIPLES = (1.0, 2.0)


def side_fee_bps(profile: str | tuple[float, float], maker_share: float = 0.0, *, allow_rebate: bool = False, adverse_selection_bps: float = 0.0) -> float:
    """Average fee per side: ``maker * share + taker * (1 - share)``.

    A negative maker fee (rebate) is refused unless ``allow_rebate=True``; then it must pass the realism envelope of
    :func:`monte_neo.verify.execution_calib.rebate_fee_bps` (rebate at most 1 bp, maker share at most 50 %, the
    ``adverse_selection_bps`` charged on maker fills, and a fee that never goes below zero).

    Raises:
        ValueError: Unknown profile name, negative fees without ``allow_rebate``, an unrealistic rebate or a maker share outside 0..1.
    """
    if isinstance(profile, str):
        if profile not in FEE_PROFILES:
            raise ValueError(f"unknown cost profile {profile!r}; known: {', '.join(sorted(FEE_PROFILES))} or a (maker, taker) pair")
        maker, taker = FEE_PROFILES[profile]
    else:
        maker, taker = float(profile[0]), float(profile[1])
    if allow_rebate and maker < 0:
        from monte_neo.verify.execution_calib import rebate_fee_bps

        return float(rebate_fee_bps(maker, taker, float(maker_share), adverse_selection_bps=adverse_selection_bps)["fee_bps"])
    if maker < 0 or taker < 0:
        raise ValueError("fees must be >= 0 bps")
    if not 0.0 <= float(maker_share) <= 1.0:
        raise ValueError(f"maker_share must be between 0 and 1, got {maker_share}")
    return maker * float(maker_share) + taker * (1.0 - float(maker_share)) + float(adverse_selection_bps) * float(maker_share) * (1.0 if allow_rebate else 0.0)


def quotes_half_spread_bps(bid: np.ndarray, ask: np.ndarray) -> dict[str, Any]:
    """Median half-spread in bps of real quotes (crossed, non-positive and non-finite quotes are dropped).

    Raises:
        ValueError: Fewer than 50 usable quotes.
    """
    b, a = np.asarray(bid, dtype=np.float64), np.asarray(ask, dtype=np.float64)
    ok = np.isfinite(b) & np.isfinite(a) & (b > 0) & (a >= b)
    if int(ok.sum()) < MIN_QUOTES:
        raise ValueError(f"only {int(ok.sum())} usable quotes; at least {MIN_QUOTES} are needed")
    half = (a[ok] - b[ok]) / (a[ok] + b[ok]) * 1e4
    return {"half_spread_bps": float(np.median(half)), "p90_half_spread_bps": float(np.percentile(half, 90)),
            "quotes": int(ok.sum()), "dropped": int((~ok).sum())}


def with_profile(model: ExecutionModel, profile: str | tuple[float, float], maker_share: float = 0.0, *, allow_rebate: bool = False, adverse_selection_bps: float = 0.0) -> ExecutionModel:
    """The model with the fee of ``profile`` as commission (slippage, impact and the rest unchanged)."""
    return replace(model, commission_bps=side_fee_bps(profile, maker_share, allow_rebate=allow_rebate, adverse_selection_bps=adverse_selection_bps), symbol_costs=())


def _scaled(model: ExecutionModel, k: float) -> ExecutionModel:
    return replace(model, commission_bps=model.commission_bps * k, slippage_bps=model.slippage_bps * k,
                   impact_bps=model.impact_bps * k, symbol_costs=tuple((s, c * k, sl * k) for s, c, sl in model.symbol_costs))


def cost_sensitivity_row(ohlc: dict[str, np.ndarray], signals: np.ndarray, model: ExecutionModel) -> dict[str, Any]:
    """Total return at 1x and 2x the modeled costs; ``warn`` when a profitable strategy is not profitable at 2x."""
    returns = {f"{k:g}x": float(_total_return(ohlc, signals, _scaled(model, k))) for k in MULTIPLES}
    base, doubled = returns["1x"], returns["2x"]
    if base <= 0.0:
        return check("cost_sensitivity", "economics", "skip", "not profitable after the modeled costs", {"returns": returns})
    text = f"total return {base:+.1%} at modeled costs, {doubled:+.1%} at doubled costs"
    if doubled <= 0.0:
        return check("cost_sensitivity", "economics", "warn", "the edge does not survive doubled costs: " + text, {"returns": returns})
    return check("cost_sensitivity", "economics", "pass", text, {"returns": returns})


def cost_realism_row(
    ohlc: dict[str, np.ndarray], signals: np.ndarray, model: ExecutionModel, half_spread_bps: float | None, source: str
) -> dict[str, Any]:
    """Re-run with fee + half-spread per side (fee from the model's commission; slippage replaced by the half-spread).

    Args:
        ohlc: OHLC arrays.
        signals: Positions.
        model: The model the backtest used.
        half_spread_bps: Half-spread per side from ``source``; ``None`` skips the row.
        source: ``"quotes"`` (a failure rejects) or ``"high-low"`` (noisy estimate: only a warning).
    """
    if half_spread_bps is None:
        return check("cost_realism", "economics", "skip", "no spread estimate (too little data and no quotes)")
    modeled = float(_total_return(ohlc, signals, model))
    if half_spread_bps <= model.mean_slip_bps:
        return check("cost_realism", "economics", "pass",
                     f"modeled slippage {model.mean_slip_bps:.1f} bps covers the {source} half-spread {half_spread_bps:.1f} bps",
                     {"source": source, "half_spread_bps": half_spread_bps, "modeled_return": modeled})
    real = float(_total_return(ohlc, signals, replace(model, slippage_bps=float(half_spread_bps), impact_bps=0.0, symbol_costs=())))
    det = {"source": source, "half_spread_bps": half_spread_bps, "modeled_slippage_bps": float(model.mean_slip_bps),
           "modeled_return": modeled, "realistic_return": real}
    text = (f"the {source} half-spread is {half_spread_bps:.1f} bps per side against {model.mean_slip_bps:.1f} bps modeled: "
            f"total return {modeled:+.1%} -> {real:+.1%} at the realistic cost")
    if modeled > 0.0 and real <= 0.0:
        return check("cost_realism", "economics", "fail" if source == "quotes" else "warn", "profit disappears at the realistic cost: " + text, det)
    return check("cost_realism", "economics", "warn", "costs look optimistic: " + text, det)


def realism_row(
    ohlc: dict[str, np.ndarray], signals: np.ndarray, model: ExecutionModel, spread: dict[str, Any], quotes_bps: float | None
) -> dict[str, Any]:
    """:func:`cost_realism_row` with the spread from real quotes when given, else from the high-low estimate."""
    if quotes_bps is not None:
        return cost_realism_row(ohlc, signals, model, float(quotes_bps), "quotes")
    return cost_realism_row(ohlc, signals, model, spread.get("half_spread_bps"), "high-low")


__all__ = [
    "realism_row", "FEE_PROFILES", "MIN_QUOTES", "cost_realism_row", "cost_sensitivity_row", "quotes_half_spread_bps", "side_fee_bps", "with_profile"]
