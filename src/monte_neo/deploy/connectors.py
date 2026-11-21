"""Deploy connectors: one table of what each execution venue can do, and the functions the runner calls through it.

A connector answers four questions for the runner: where the daily signal bars come from (public mainnet data), what
price marks the book, how the demo account is reached (a testnet client, or the in-memory :class:`SimExchange` for dry
runs), and what the venue allows (short selling, gross exposure). Funding of perpetual futures is charged to both
virtual books from the public mainnet funding history, so a market-neutral book pays what a real one would.

Venues with a connector:

* ``binance_spot``: Binance spot testnet. Long-only, gross exposure at most 1 (no leverage).
* ``binance_usdm``: Binance USD-M perpetual futures testnet. Long and short; gross exposure (sum of absolute weights)
  at most ``max_gross`` (1 by default, 2 at most), so a market-neutral book of 0.5 long and 0.5 short uses gross 1.

Every other venue of ``catalog compat`` is listed there as ``planned``. Only demo accounts are ever traded: a connector
has no setting that points signed requests at a mainnet host.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from monte_neo.deploy import binance

MAX_GROSS_LIMIT = 2.0


@dataclass(frozen=True)
class Venue:
    id: str
    market: str  # the --market value that selects it
    short: bool
    max_gross: float
    funding: bool
    signed_host: str
    key_env: tuple[str, str]
    keychain: tuple[str, str]
    note: str


VENUES: dict[str, Venue] = {
    "binance_spot": Venue("binance_spot", "spot", short=False, max_gross=1.0, funding=False, signed_host=binance.SPOT_TESTNET,
                          key_env=("MONTE_NEO_TESTNET_KEY", "MONTE_NEO_TESTNET_SECRET"),
                          keychain=("monte_neo_testnet_key", "monte_neo_testnet_secret"),
                          note="spot testnet, long-only, no leverage"),
    "binance_usdm": Venue("binance_usdm", "usdm", short=True, max_gross=MAX_GROSS_LIMIT, funding=True, signed_host=binance.FUTURES_TESTNET,
                          key_env=("MONTE_NEO_FUTURES_TESTNET_KEY", "MONTE_NEO_FUTURES_TESTNET_SECRET"),
                          keychain=("monte_neo_futures_testnet_key", "monte_neo_futures_testnet_secret"),
                          note="USD-M perpetual futures testnet, long and short, funding charged from mainnet history"),
}
BY_MARKET = {v.market: v for v in VENUES.values()}


def venue(cfg_or_id: dict[str, Any] | str | None) -> Venue:
    """The venue of a run's start entry (runs started before connectors existed are spot) or of an id / market name."""
    if isinstance(cfg_or_id, dict):
        key = cfg_or_id.get("venue", "binance_spot")
    else:
        key = cfg_or_id or "binance_spot"
    if key in VENUES:
        return VENUES[key]
    if key in BY_MARKET:
        return BY_MARKET[key]
    raise ValueError(f"no deploy connector for {key!r}: available {', '.join(sorted(VENUES))} (others are planned, see `monte-neo catalog compat`)")


def klines_fn(v: Venue) -> Callable[..., list[tuple[int, float]]]:
    """Signal and mark bars: mainnet daily closes of the instrument actually traded."""
    return binance.futures_daily_klines if v.id == "binance_usdm" else binance.daily_klines


def price_fn(v: Venue) -> Callable[[str], float]:
    return binance.futures_price if v.id == "binance_usdm" else binance.mainnet_price


def exchange(v: Venue, mode: str, *, capital: float, fee_bps: float, slippage_bps: float, keys: tuple[str, str] | None = None) -> Any:
    """The demo account client for ``mode`` testnet, or the dry-run simulator for paper and dry runs."""
    if mode != "testnet":
        return binance.SimExchange(cash=capital, slippage_bps=slippage_bps, fee_bps=fee_bps)
    if keys is None:
        raise ValueError(f"mode testnet on {v.id} needs its testnet keys: set {v.key_env[0]} and {v.key_env[1]}, or run `monte-neo deploy keys`")
    cls = binance.FuturesTestnet if v.id == "binance_usdm" else binance.SpotTestnet
    return cls(key=keys[0], secret=keys[1])


def funding_payment(qty: float, events: list[tuple[int, float, float | None]], fallback_price: float) -> float:
    """USDT received by a position of ``qty`` (negative = short) over the funding events: a long pays a positive rate."""
    return float(sum(-qty * (mp if mp else fallback_price) * rate for _, rate, mp in events))


def describe() -> list[dict[str, Any]]:
    return [{"venue": v.id, "market": v.market, "short": v.short, "max_gross": v.max_gross, "funding": v.funding, "note": v.note}
            for v in VENUES.values()]
