"""A15 alpha zoo: synthetic cross-sections with a known flaw (trap) and an honest twin that has the same shape.

Every generator takes a seed and returns a :class:`Case`: long price and score tables, the keyword arguments for
``validate_alpha`` and the checks that must react (trap) or must stay quiet (twin). Everything is deterministic in
the seed. Forward returns are built from the scores in the generator only; the verifier never sees them.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

N_SYM = 40
N_DAY = 1000
PLACEBOS = 60
AUM = 1e6
START = "2018-01-01"


@dataclass(frozen=True)
class Expect:
    """A check id and the statuses allowed for it (for a trap: the statuses that count as caught)."""

    check: str
    statuses: tuple[str, ...]


@dataclass
class Case:
    """One zoo case: inputs for ``validate_alpha`` plus what the verifier must say."""

    name: str
    trap: bool
    prices: pd.DataFrame
    scores: pd.DataFrame
    expect: list[Expect]
    kwargs: dict[str, Any] = field(default_factory=dict)


def _rng(seed: int, name: str) -> np.random.Generator:
    return np.random.default_rng([seed, zlib.crc32(name.encode())])


def _ar1(rng: np.random.Generator, t: int, n: int, phi: float) -> np.ndarray:
    """Unit-variance AR(1) panel (t, n); ``phi`` = 0 gives independent draws."""
    out = np.empty((t, n))
    out[0] = rng.standard_normal(n)
    scale = float(np.sqrt(1.0 - phi * phi))
    for i in range(1, t):
        out[i] = phi * out[i - 1] + scale * rng.standard_normal(n)
    return out


def _symbols(n: int) -> list[str]:
    return [f"S{i:02d}" for i in range(n)]


def _dates(t: int) -> pd.DatetimeIndex:
    return pd.bdate_range(START, periods=t)


def _close(fwd: np.ndarray) -> np.ndarray:
    """Close prices from forward returns: ``close[t+1] = close[t] * (1 + fwd[t])``."""
    close = np.empty_like(fwd)
    close[0] = 100.0
    close[1:] = 100.0 * np.cumprod(1.0 + fwd[:-1], axis=0)
    return close


def _market(rng: np.random.Generator, t: int, drift: float = 0.0003, vol: float = 0.008) -> np.ndarray:
    return drift + vol * rng.standard_normal(t)


def _tables(
    dates: pd.DatetimeIndex, syms: list[str], close: np.ndarray, volume: np.ndarray | float, scores: np.ndarray
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long price and score tables; NaN prices and NaN scores are dropped (delisted or unscored names)."""
    t, n = close.shape
    vol = np.broadcast_to(np.asarray(volume, dtype=float), (t, n))
    stamps = np.repeat(dates.to_numpy(), n)
    names = np.tile(syms, t)
    prices = pd.DataFrame({"timestamp": stamps, "symbol": names, "close": close.ravel(), "volume": vol.ravel()})
    score = pd.DataFrame({"timestamp": stamps, "symbol": names, "score": scores.ravel()})
    return prices.dropna(subset=["close"]).reset_index(drop=True), score.dropna(subset=["score"]).reset_index(drop=True)


def _plain(rng: np.random.Generator, edge: float, t: int = N_DAY, n: int = N_SYM, phi: float = 0.9, trend: float = 0.0):
    """A world where the score ``a`` (AR(1)) predicts the next return with strength ``edge`` per unit of score."""
    a = _ar1(rng, t, n, phi)
    latent = trend * _ar1(rng, t, n, 0.99) if trend else 0.0
    fwd = _market(rng, t)[:, None] + edge * a + latent + 0.02 * rng.standard_normal((t, n))
    return a, fwd


def _case(name: str, trap: bool, dates, syms, fwd, scores, expect, volume=1e6, **kwargs) -> Case:  # noqa: ANN001
    prices, score = _tables(dates, syms, _close(fwd), volume, scores)
    return Case(name, trap, prices, score, expect, {"aum": AUM, "placebos": PLACEBOS, **kwargs})


def _momentum(close: np.ndarray) -> np.ndarray:
    """A 12-1 month momentum score with a one-day different skip: not bit-identical to the verifier's factor."""
    c = pd.DataFrame(close)
    return (c.shift(21) / c.shift(250) - 1.0).to_numpy()


# --- 1 residual_alpha ---------------------------------------------------------------------------------------------

def repackaged_momentum(seed: int, trap: bool = True) -> Case:
    """The score is past 12-1 momentum in a world with a momentum premium; the twin plants an independent signal."""
    rng = _rng(seed, "momentum")
    a, fwd = _plain(rng, 0.0 if trap else 0.0009, trend=0.002)
    syms, dates = _symbols(N_SYM), _dates(N_DAY)
    scores = _momentum(_close(fwd)) if trap else a
    name = "repackaged_momentum" if trap else "independent_signal"
    return _case(name, trap, dates, syms, fwd, scores, [Expect("residual_alpha", ("fail", "warn") if trap else ("pass",))] +
                 ([Expect("ic", ("info",))] if trap else []))


# --- 2 hidden_short_volatility ----------------------------------------------------------------------------------

def short_volatility(seed: int, trap: bool = True) -> Case:
    """Steady spread that gives it all back when the market falls; the twin has the same shocks with a symmetric payoff."""
    rng = _rng(seed, "shortvol")
    a, fwd = _plain(rng, 0.0006)
    shock = rng.random(N_DAY) < 0.015
    z = np.where(shock[:, None], a, 0.0)
    alternate = np.where(np.cumsum(shock) % 2 == 0, 1.0, -1.0)[:, None]  # twin: shocks hit the spread up and down in turn
    sign = 1.0 if trap else alternate
    fwd = fwd - 0.03 * z * sign - 0.03 * shock[:, None]
    syms, dates = _symbols(N_SYM), _dates(N_DAY)
    name = "short_volatility" if trap else "symmetric_payoff"
    return _case(name, trap, dates, syms, fwd, a, [Expect("hidden_short_volatility", ("warn", "fail") if trap else ("pass",))])


# --- 3 universe_subsampling ---------------------------------------------------------------------------------------

def three_symbols(seed: int, trap: bool = True) -> Case:
    """All the edge sits in three names; the twin spreads the same edge over every name."""
    rng = _rng(seed, "three")
    a = _ar1(rng, N_DAY, N_SYM, 0.9)
    coef = np.full(N_SYM, 0.0012)
    if trap:
        coef = np.zeros(N_SYM)
        coef[rng.choice(N_SYM, 3, replace=False)] = 0.012
    fwd = _market(rng, N_DAY)[:, None] + coef * a + 0.02 * rng.standard_normal((N_DAY, N_SYM))
    name = "three_symbols" if trap else "spread_edge"
    return _case(name, trap, _dates(N_DAY), _symbols(N_SYM), fwd, a, [Expect("universe_subsampling", ("warn", "fail") if trap else ("pass",))])


# --- 4 rebalance_timing_luck ------------------------------------------------------------------------------------

def first_day_of_month(seed: int, trap: bool = True) -> Case:
    """The score only pays on the first trading day of each month; the twin pays uniformly with a slow signal."""
    rng = _rng(seed, "firstday")
    dates = _dates(N_DAY)
    if trap:
        z = rng.standard_normal((N_DAY, N_SYM))
        first = np.r_[False, (dates.month[1:] != dates.month[:-1])]  # first trading day of a month
        paid = np.r_[first[1:], False]  # the score of the day before pays on that day
        fwd = _market(rng, N_DAY)[:, None] + 0.012 * paid[:, None] * z + 0.02 * rng.standard_normal((N_DAY, N_SYM))
        a = z
    else:
        a, fwd = _plain(rng, 0.0006, phi=0.97)
    name = "first_day_of_month" if trap else "uniform_edge"
    return _case(name, trap, dates, _symbols(N_SYM), fwd, a, [Expect("rebalance_timing_luck", ("warn",) if trap else ("pass",))])


# --- 5 short_feasibility -------------------------------------------------------------------------------------------

def illiquid_shorts(seed: int, trap: bool = True) -> Case:
    """Low scores sit in thinly traded microcaps; the twin's volume has nothing to do with the score."""
    rng = _rng(seed, "illiquid")
    a, fwd = _plain(rng, 0.0008)
    liq = rng.standard_normal(N_SYM)
    volume = 2e5 * np.exp(1.2 * liq)[None, :] * np.ones((N_DAY, 1))
    scores = a + 2.0 * liq[None, :] if trap else a
    name = "illiquid_shorts" if trap else "liquid_shorts"
    return _case(name, trap, _dates(N_DAY), _symbols(N_SYM), fwd, scores, [Expect("short_feasibility", ("warn",) if trap else ("pass",))], volume=volume)


# --- 6 universe_lookahead ------------------------------------------------------------------------------------------

def survivor_universe(seed: int, trap: bool = True) -> Case:
    """Six years of today's members with nobody added or removed; the twin's names come and go."""
    rng = _rng(seed, "survivor")
    t, n = 1560, 30
    a, fwd = _plain(rng, 0.0005, t=t, n=n)
    close = _close(fwd)
    if not trap:
        for j in range(0, 6):
            close[int(rng.integers(300, t - 100)) :, j] = np.nan  # delisted
        for j in range(6, 12):
            close[: int(rng.integers(100, 600)), j] = np.nan  # listed late
    syms, dates = _symbols(n), _dates(t)
    prices, score = _tables(dates, syms, close, 1e6, np.where(np.isfinite(close), a, np.nan))
    name = "survivor_universe" if trap else "names_come_and_go"
    return Case(name, trap, prices, score, [Expect("universe_lookahead", ("warn",) if trap else ("info", "pass"))], {"aum": AUM, "placebos": PLACEBOS})


def membership_window(seed: int, trap: bool = True) -> Case:
    """Names that joined the index late are scored and held before they joined; the twin scores them only inside the window."""
    rng = _rng(seed, "member")
    t, n = 800, 30
    a, fwd = _plain(rng, 0.0005, t=t, n=n)
    syms, dates = _symbols(n), _dates(t)
    late = sorted(rng.choice(n, 8, replace=False).tolist())
    join = int(0.5 * t)
    scores = a.copy()
    if not trap:
        scores[:join, late] = np.nan
    rows = [{"symbol": s, "start": "", "end": ""} for i, s in enumerate(syms) if i not in late]
    rows += [{"symbol": syms[i], "start": dates[join].strftime("%Y-%m-%d"), "end": ""} for i in late]
    name = "membership_ignored" if trap else "membership_respected"
    return _case(name, trap, dates, syms, fwd, scores, [Expect("universe_lookahead", ("fail",) if trap else ("pass",))], membership=pd.DataFrame(rows))


# --- 7 cross_market_close_alignment ------------------------------------------------------------------------------

def same_date_new_york(seed: int, trap: bool = True) -> Case:
    """Tokyo names scored with the New York return of the same date (NY closes later); the twin uses the previous date."""
    rng = _rng(seed, "crossmarket")
    t, k = 800, 20
    v = _ar1(rng, t, k, 0.0 if trap else 0.9)
    mkt = _market(rng, t)[:, None]
    # daily[d] is the return from d-1 to d; Tokyo's day d depends on v[d-1], the New York peer's day d shows v[d]
    asia_daily = np.vstack([np.zeros((1, k)), 0.004 * v[:-1]]) + mkt + 0.02 * rng.standard_normal((t, k))
    ny_daily = 0.02 * v + mkt + 0.01 * rng.standard_normal((t, k))
    peer = ny_daily if trap else np.vstack([np.full((1, k), np.nan), ny_daily[:-1]])
    fwd_asia, fwd_ny = np.vstack([asia_daily[1:], np.zeros((1, k))]), np.vstack([ny_daily[1:], np.zeros((1, k))])
    fwd = np.hstack([fwd_asia, fwd_ny])
    scores = np.hstack([peer, np.full((t, k), np.nan)])
    syms = [f"T{i:02d}" for i in range(k)] + [f"N{i:02d}" for i in range(k)]
    exchanges = {s: "XTKS" if s.startswith("T") else "XNYS" for s in syms}
    name = "same_date_new_york" if trap else "lagged_new_york"
    return _case(name, trap, _dates(t), syms, fwd, scores, [Expect("cross_market_close_alignment", ("warn", "fail") if trap else ("pass",))], exchanges=exchanges)


# --- 8 post_discovery_decay --------------------------------------------------------------------------------------

def dies_after_discovery(seed: int, trap: bool = True) -> Case:
    """The edge is gone after the publication date; the twin keeps its edge."""
    rng = _rng(seed, "decay")
    a = _ar1(rng, N_DAY, N_SYM, 0.9)
    cut = int(0.55 * N_DAY)
    edge = np.full(N_DAY, 0.0008)
    if trap:
        edge[cut:] = 0.0
    fwd = _market(rng, N_DAY)[:, None] + edge[:, None] * a + 0.02 * rng.standard_normal((N_DAY, N_SYM))
    dates = _dates(N_DAY)
    name = "dies_after_discovery" if trap else "persistent_edge"
    return _case(name, trap, dates, _symbols(N_SYM), fwd, a, [Expect("post_discovery_decay", ("warn",) if trap else ("info",))],
                 discovery_date=dates[cut].strftime("%Y-%m"))


# --- 9 signal_placebo, synthetic_market_null ------------------------------------------------------------------------

def noise_score(seed: int, trap: bool = True) -> Case:
    """A score unrelated to returns; the twin has a real weak edge."""
    rng = _rng(seed, "noise")
    a, fwd = _plain(rng, 0.0 if trap else 0.0005)
    scores = _ar1(rng, N_DAY, N_SYM, 0.9) if trap else a
    name = "noise_score" if trap else "weak_real_edge"
    want = ("fail",) if trap else ("pass",)
    return _case(name, trap, _dates(N_DAY), _symbols(N_SYM), fwd, scores, [Expect("signal_placebo", want), Expect("synthetic_market_null", want)])


# --- 10 marginal_sharpe ---------------------------------------------------------------------------------------------

def book_clone(seed: int, trap: bool = True) -> Case:
    """The fund's book is a noisy copy of this strategy; the twin is added to an independent book."""
    from monte_neo.alpha.families_run import portfolio_returns
    from monte_neo.alpha.panel import build_panel

    rng = _rng(seed, "book")
    a, fwd = _plain(rng, 0.0006)
    syms, dates = _symbols(N_SYM), _dates(N_DAY)
    case = _case("book_clone" if trap else "independent_book", trap, dates, syms, fwd, a, [Expect("marginal_sharpe", ("warn",) if trap else ("pass",))])
    own, _ = portfolio_returns(build_panel(case.prices, case.scores), 5)
    if trap:
        book = 0.5 * own + 0.1 * own.std() * rng.standard_normal(N_DAY)
    else:
        book = 0.0005 + 0.006 * rng.standard_normal(N_DAY)
    case.kwargs["book"] = pd.DataFrame({"date": dates, "fund": book})
    return case


# --- 11 noise_injection ---------------------------------------------------------------------------------------------

def exact_values(seed: int, trap: bool = True) -> Case:
    """The edge lives in tiny differences under huge outliers, so a little noise erases it; the twin ranks robustly."""
    rng = _rng(seed, "exact")
    a, fwd = _plain(rng, 0.0008)
    scores = a.copy()
    if trap:
        scores = 1e-3 * a
        for i in range(N_DAY):
            hit = rng.choice(N_SYM, 3, replace=False)
            scores[i, hit] += 1e3 * rng.choice([-1.0, 1.0], 3)
    name = "exact_values" if trap else "robust_ranking"
    return _case(name, trap, _dates(N_DAY), _symbols(N_SYM), fwd, scores, [Expect("noise_injection", ("warn",) if trap else ("pass",))])


# --- 12 breadth_consistency -----------------------------------------------------------------------------------------

def inflated_claim(seed: int, trap: bool = True) -> Case:
    """A claimed IR several times what IC and breadth allow; the twin claims what the fundamental law gives."""
    from monte_neo.alpha._core import ic_series

    rng = _rng(seed, "claim")
    a, fwd = _plain(rng, 0.0004)
    mean_ic = float(np.nanmean(ic_series(a[:-1], fwd[:-1])))
    implied = mean_ic * float(np.sqrt(N_SYM * 252.0))
    claim = 6.0 * implied if trap else 0.9 * implied
    name = "inflated_claim" if trap else "honest_claim"
    return _case(name, trap, _dates(N_DAY), _symbols(N_SYM), fwd, a, [Expect("breadth_consistency", ("warn",) if trap else ("pass",))], claimed_ir=claim)


GENERATORS: dict[str, Callable[..., Case]] = {
    "residual_alpha": repackaged_momentum,
    "hidden_short_volatility": short_volatility,
    "universe_subsampling": three_symbols,
    "rebalance_timing_luck": first_day_of_month,
    "short_feasibility": illiquid_shorts,
    "universe_lookahead_warn": survivor_universe,
    "universe_lookahead_fail": membership_window,
    "cross_market_close_alignment": same_date_new_york,
    "post_discovery_decay": dies_after_discovery,
    "signal_placebo": noise_score,
    "marginal_sharpe": book_clone,
    "noise_injection": exact_values,
    "breadth_consistency": inflated_claim,
}


def run_case(case: Case, seed: int = 0) -> dict[str, Any]:
    """Run ``validate_alpha`` on a case; returns the report (statuses via :func:`statuses`)."""
    from monte_neo.alpha import validate_alpha

    return validate_alpha(case.prices, case.scores, seed=seed, **case.kwargs)


def statuses(report: dict[str, Any]) -> dict[str, str]:
    """Check id -> status of a report."""
    return {c["id"]: c["status"] for c in report["checks"]}


def met(case: Case, report: dict[str, Any]) -> dict[str, bool]:
    """For every expectation of the case: did the report give one of the allowed statuses?"""
    status = statuses(report)
    return {e.check: status.get(e.check) in e.statuses for e in case.expect}
