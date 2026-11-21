"""``alpha-report/1``: run the family A checks and assemble the report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
from monte_neo.alpha.families_run import NEXT_ACTIONS as BCFI_ACTIONS
from monte_neo.alpha.families_run import run_families
from monte_neo.alpha.implementability_run import NEXT_ACTIONS as D_ACTIONS
from monte_neo.alpha.implementability_run import run_implementability
from monte_neo.alpha.panel import Panel, build_panel, data_sha256
from monte_neo.alpha.signal_power import (
    check_breadth_consistency,
    check_ic,
    check_ic_decay,
    check_long_short_legs,
    check_quantile_monotonicity,
    check_selection_vs_timing,
    check_signal_placebo,
)
from monte_neo.disclaimer import ALPHA_SCOPE, SHORT
from monte_neo.verify.schema import aggregate_verdict, to_jsonable

ALPHA_SCHEMA_ID = "alpha-report/1"

NEXT_ACTIONS: dict[str, str] = {
    "ic": "The score shows no reliable rank link to later returns: test more history or more symbols, or rebuild the signal; do not trade it on this evidence.",
    "ic_decay": "Match the holding period to the horizon where the IC peaks and trade no slower than the half-life.",
    "quantile_monotonicity": "Bucket returns are not ordered: the score may only work in one tail. Test a tail-only rule on new data, or check for outliers driving the extreme bucket.",
    "long_short_legs": "Most profit comes from shorting: re-test long-only, or price borrow cost, short bans and microcap liquidity before trusting the spread.",
    "breadth_consistency": "The claimed IR is above what IC and breadth allow: report the implied IR, or find out which costs, leverage or overlap inflate the claim.",
    "signal_placebo": "Random scores earn about as much as yours: the long-short construction or the market drift earns, not the signal. Re-test with market-neutral returns and more history.",
    "selection_vs_timing": "If the spread survives with dates shuffled, a persistent tilt (a fixed set of winners) earns, not the score: neutralise sector, size and momentum exposures.",
}


def demo_panel(seed: int = 0, n_symbols: int = 40, n_days: int = 750) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Synthetic universe with a weakly predictive score (IC about 0.04) and a pure-noise score.

    Args:
        seed: Random seed.
        n_symbols: Number of symbols.
        n_days: Number of business days.

    Returns:
        (prices, real_scores, noise_scores) as long tables.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n_days, n_symbols))
    noise = rng.standard_normal((n_days, n_symbols))
    market = 0.0003 + 0.008 * rng.standard_normal((n_days, 1))
    ret = market + 0.0012 * z + 0.02 * noise  # return from day t to t+1 depends on the score of day t
    close = 100.0 * np.cumprod(1.0 + np.vstack([np.zeros((1, n_symbols)), ret[:-1]]), axis=0)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    syms = [f"S{i:02d}" for i in range(n_symbols)]
    prices = pd.DataFrame({"timestamp": np.repeat(dates, n_symbols), "symbol": np.tile(syms, n_days), "close": close.ravel(), "volume": 1e6})

    def table(m: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame({"timestamp": np.repeat(dates, n_symbols), "symbol": np.tile(syms, n_days), "score": m.ravel()})

    return prices, table(z), table(rng.standard_normal((n_days, n_symbols)))


def _next_actions(checks: list[dict[str, Any]]) -> list[str]:
    actions = {**NEXT_ACTIONS, **D_ACTIONS, **BCFI_ACTIONS}
    return [actions[c["id"]] for s in ("fail", "warn") for c in checks if c["status"] == s and c["id"] in actions]


def run_checks(panel: Panel, *, horizon: int, quantiles: int, claimed_ir: float | None, seed: int, placebos: int) -> list[dict[str, Any]]:
    """Run family A on an aligned panel (forward returns are used only as targets)."""
    fwd = panel.forward_returns(horizon)
    ic = check_ic(panel, fwd, horizon)
    mean_ic = ic["details"].get("mean_ic", float("nan"))
    return [
        ic,
        check_ic_decay(panel),
        check_quantile_monotonicity(panel, fwd, quantiles, seed),
        check_long_short_legs(panel, fwd, quantiles),
        check_breadth_consistency(panel, mean_ic, horizon, claimed_ir),
        check_signal_placebo(panel, fwd, quantiles, seed, placebos),
        check_selection_vs_timing(panel, fwd, quantiles, seed),
    ]


def validate_alpha(
    prices: pd.DataFrame | str | Path,
    scores: pd.DataFrame | str | Path,
    *,
    horizon: int = 1,
    quantiles: int = 5,
    claimed_ir: float | None = None,
    seed: int = 0,
    placebos: int = 200,
    aum: float | None = None,
    factors: str | Path | None = None,
    book: str | Path | pd.DataFrame | None = None,
    n_trials: int = 1,
    families: bool = True,
    membership: str | Path | pd.DataFrame | None = None,
    groups: str | Path | pd.DataFrame | None = None,
    exchanges: str | Path | dict[str, str] | None = None,
    discovery_date: str | None = None,
    existing: str | Path | pd.DataFrame | None = None,
    funding: str | Path | pd.DataFrame | None = None,
    aum_grid: list[float] | None = None,
    min_capacity: float | None = None,
    liquid_top: int | None = None,
    liquid_lookback: int = 30,
    terminal_returns: dict[str, float] | None = None,
    rebalance_phase: str | None = None,
    ledger: bool | str | Path | None = None,
) -> dict[str, Any]:
    """Check whether a cross-sectional score has real predictive power and whether its portfolio can be traded.

    Args:
        prices: Long table (timestamp, symbol, close[, volume]) or a .csv / .parquet path.
        scores: Long table (timestamp, symbol, score) or a path.
        horizon: Forward-return horizon in bars.
        quantiles: Number of quantile buckets.
        claimed_ir: Claimed annual information ratio (enables the breadth check).
        seed: Seed for bootstraps and placebos.
        placebos: Number of permuted-score placebos.
        aum: Capital for the market-impact and participation checks (family D); ``None`` skips those two.
        factors: Factor returns file for attribution (family B); default: factors built from the universe.
        book: Returns of an existing book (family C); ``None`` skips the family.
        n_trials: Variants tried before this one (family F).
        families: Run families B, C, E, F, G and I on the score's long-short portfolio (default True).
        membership: When each symbol was in the universe (symbol, start, end): look-ahead through today's members.
        groups: Sector or country per symbol (symbol, group[, as_of]): robustness by group, classification look-ahead.
        exchanges: Exchange per symbol (a dict, or a file with symbol, exchange): closes of different markets.
        discovery_date: When the anomaly was published or found (``YYYY-MM``): decay after discovery.
        existing: Scores of signals already run (timestamp, symbol, one column per signal): partial IC of the new one.
        funding: Funding history (timestamp, symbol, funding_bps a long pays per bar): priced on every perpetual leg, short legs included.
        aum_grid: AUMs (quote currency) for the capacity grid in one run, for example 250000, 500000, 5000000.
        min_capacity: AUM at which the net return must stay positive (default: the largest of the grid).
        liquid_top: Trade only the K most liquid symbols by traded value known before each date (a point-in-time universe, membership derived).
        liquid_lookback: Bars of trailing traded value for ``liquid_top`` (default 30).
        terminal_returns: Return a delisted symbol gets on the bar after its last price (``{symbol: -0.9}``); undeclared ones are flagged.
        rebalance_phase: ``K/H``: rebalance on bar K of every H and hold the scores in between, to run the whole report for one phase.

    Returns:
        An ``alpha-report/1`` dict: verdict, checks, metrics, next_actions, reproducibility.

    Raises:
        ValueError: if the inputs cannot be aligned (duplicates, unknown symbols, late scores, ...).
    """
    if quantiles < 2:
        raise ValueError("quantiles must be >= 2")
    trial_book, ledger_rows, data_id, variant = None, [], "", ""
    if ledger:  # count every score variant tried on these prices; levels 4 and above need this evidence (arl-rules/2)
        from monte_neo.verify.ledger import Ledger, ledger_row

        trial_book = Ledger(None if ledger is True else ledger)
        data_id, variant = str(data_sha256(prices))[:16], "scores:" + str(data_sha256(scores))[:16]
        counted = trial_book.count_with(variant, data_id)
        lrow = ledger_row(counted, n_trials, trial_book.check(), trial_book.path)
        n_trials = max(int(n_trials or 1), counted)
        if lrow["status"] != "pass":
            lrow["status"] = "info"  # context only: a recheck has no ledger, so it must not move the verdict
        ledger_rows = [lrow]
    panel = build_panel(prices, scores)
    from monte_neo.alpha import universe_tools as ut

    panel, extra_rows, derived_membership = ut.prepare_panel(panel, liquid_top=liquid_top, liquid_lookback=liquid_lookback,
                                                           terminal_returns=terminal_returns, rebalance_phase=rebalance_phase)
    checks = run_checks(panel, horizon=horizon, quantiles=quantiles, claimed_ir=claimed_ir, seed=seed, placebos=placebos)
    half_life = next((c["details"].get("half_life") for c in checks if c["id"] == "ic_decay"), None)
    from monte_neo.alpha.funding_cost import load_funding

    checks += extra_rows + ledger_rows
    from monte_neo.alpha.executable import cost_sensitivity_row, executable_returns
    from monte_neo.alpha.implementability_run import portfolio_weights

    funding_m = load_funding(funding, panel) if funding is not None else None
    w_exec = portfolio_weights(panel, quantiles)
    net, net_info = executable_returns(w_exec, panel.close, panel.volume, aum, funding_bps=funding_m)
    checks.append(cost_sensitivity_row(w_exec, panel.close, panel.volume, aum, panel.periods_per_year, funding_m))
    checks += run_implementability(panel, quantiles=quantiles, aum=aum, half_life=half_life, funding_bps=funding_m,
                                   aum_grid=aum_grid, min_capacity=min_capacity)
    if families:
        from monte_neo.alpha.families_inputs import process_inputs

        process, group_map = process_inputs(membership if membership is not None else derived_membership, groups, exchanges, discovery_date)
        checks += run_families(panel, quantiles=quantiles, factors=factors, book=book, n_trials=n_trials, seed=seed,
                               process=process, groups=group_map, existing=existing, net_returns=net, net_costs=net_info["costs"])
    by = {c["id"]: c["details"] for c in checks}
    metrics = {
        "n_dates": len(panel.dates), "n_symbols": len(panel.symbols),
        "mean_ic": by["ic"].get("mean_ic"), "ic_t_stat": by["ic"].get("t_stat"), "icir": by["ic"].get("icir"),
        "best_horizon": by["ic_decay"].get("best_horizon"), "ic_half_life": by["ic_decay"].get("half_life"),
        "quantile_spread": by["quantile_monotonicity"].get("spread"), "short_leg_share": by["long_short_legs"].get("short_share"),
        "placebo_p_value": by["signal_placebo"].get("p_value"), "implied_ir": by["breadth_consistency"].get("implied_ir"),
        "score_rows_not_on_price_dates": panel.n_unmatched_score_rows,
        "aum_where_sharpe_halves": by["capacity_curve"].get("aum_half"),
    }
    report = to_jsonable({
        "schema": ALPHA_SCHEMA_ID,
        "verdict": aggregate_verdict(checks),
        "checks": checks,
        "metrics": metrics,
        "next_actions": _next_actions(checks),
        "reproducibility": {
            "data_sha256": {"prices": data_sha256(prices), "scores": data_sha256(scores)},
            "settings": {"horizon": horizon, "quantiles": quantiles, "claimed_ir": claimed_ir, "seed": seed, "placebos": placebos, "aum": aum,
                         "factors": data_sha256(factors) if factors else None,
                         "book": data_sha256(book) if book is not None else None, "n_trials": n_trials, "families": families,
                         "membership": data_sha256(membership) if membership is not None else None,
                         "groups": data_sha256(groups) if groups is not None else None,
                         "exchanges": exchanges if isinstance(exchanges, dict) else (data_sha256(exchanges) if exchanges else None),
                         "discovery_date": discovery_date,
                         "existing": data_sha256(existing) if existing is not None else None,
                         **({"funding": data_sha256(funding)} if funding is not None else {}),
                         **({"aum_grid": list(aum_grid)} if aum_grid else {}), **({"min_capacity": min_capacity} if min_capacity is not None else {}),
                         **({"liquid_top": liquid_top, "liquid_lookback": liquid_lookback} if liquid_top else {}),
                         **({"terminal_returns": terminal_returns} if terminal_returns is not None else {}), **({"rebalance_phase": rebalance_phase} if rebalance_phase else {})},
            "engine_version": __version__,
        },
        "disclaimer": f"{ALPHA_SCOPE} {SHORT}",
    })
    from monte_neo.verify.verdict import certificate_id

    report["certificate_id"] = certificate_id(report["reproducibility"], report["verdict"])
    if trial_book is not None:
        m = report["metrics"]
        sharpe = m.get("net_sharpe", m.get("sharpe", 0.0))
        trial_book.record(variant=variant, data_id=data_id, sharpe=float(sharpe or 0.0), verdict=report["verdict"],
                          certificate_id=report["certificate_id"])
    from monte_neo.readiness import readiness

    report["readiness"] = readiness(alpha=report)
    return report


def recheck_alpha(
    certificate: dict[str, Any], prices: pd.DataFrame | str | Path, scores: pd.DataFrame | str | Path, *,
    factors: str | Path | None = None, book: str | Path | pd.DataFrame | None = None,
    membership: str | Path | pd.DataFrame | None = None, groups: str | Path | pd.DataFrame | None = None,
    existing: str | Path | pd.DataFrame | None = None, exchanges: str | Path | dict[str, str] | None = None,
    funding: str | Path | pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Re-run an ``alpha-report/1`` with its stored settings and compare the certificate id.

    Inputs that the report only stored as hashes (``factors``, ``book``, ``membership``, ``groups``, ``existing``, a file of ``exchanges``) must be
    given again; a different file gives a different id.

    Returns:
        ``{"reproduced", "certificate_id", "expected_id", "verdict", "data_matches"}``.
    """
    repro = certificate.get("reproducibility", {})
    st = repro.get("settings", {})
    fresh = validate_alpha(
        prices, scores, horizon=int(st.get("horizon", 1)), quantiles=int(st.get("quantiles", 5)), claimed_ir=st.get("claimed_ir"),
        seed=int(st.get("seed", 0)), placebos=int(st.get("placebos", 200)), aum=st.get("aum"), factors=factors, book=book,
        n_trials=int(st.get("n_trials", 1)), families=bool(st.get("families", True)), membership=membership, groups=groups,
        exchanges=exchanges if exchanges is not None else (st.get("exchanges") if isinstance(st.get("exchanges"), dict) else None), discovery_date=st.get("discovery_date"),
        existing=existing, funding=funding, aum_grid=st.get("aum_grid"), min_capacity=st.get("min_capacity"),
        liquid_top=st.get("liquid_top"), liquid_lookback=int(st.get("liquid_lookback", 30)), terminal_returns=st.get("terminal_returns"),
        rebalance_phase=st.get("rebalance_phase"),
    )
    return {
        "reproduced": fresh["certificate_id"] == certificate.get("certificate_id"),
        "certificate_id": fresh["certificate_id"], "expected_id": certificate.get("certificate_id"), "verdict": fresh["verdict"],
        "data_matches": fresh["reproducibility"]["data_sha256"] == repro.get("data_sha256"),
    }
