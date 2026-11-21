"""The daily job: mark both books, rebalance on schedule, enforce the kill switch. Idempotent and resumable.

``run_day(D)`` can be called any number of times for the same UTC day D: every step first looks for its own journal
entry and skips when it is there, so a restart after a power or network cut continues where it stopped. Days that were
missed are recorded late with ``late: true`` (never back-filled silently). Signals use only mainnet daily bars that
closed before D; orders go to the spot testnet (or the dry-run exchange) with deterministic client ids.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

from monte_neo.deploy import account, binance, plugin
from monte_neo.deploy.journal import Journal

LOOKBACK = 500  # daily bars handed to the plug-in


class RunError(RuntimeError):
    """The journal is not in a state the runner can continue from."""


def utc_today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def start_entry(journal: Journal, body: dict[str, Any]) -> dict[str, Any]:
    if journal.find("start"):
        raise RunError("the journal already has a start entry; a new run needs a new journal (--run NAME)")
    return journal.append("start", body)


def config(journal: Journal) -> dict[str, Any]:
    st = journal.find("start")
    if not st:
        raise RunError("no start entry: run `monte-neo deploy init` first")
    return st[0]["body"]  # type: ignore[no-any-return]


def books_for(mode: str) -> list[str]:
    return ["paper"] if mode == "paper" else ["paper", "testnet"]


def is_rebalance_day(cfg: dict[str, Any], day: dt.date) -> bool:
    return cfg["rebalance"] == "daily" or day.weekday() == int(cfg.get("weekday", 0))


def _bars(symbol: str, day: dt.date, n: int) -> list[tuple[int, float]]:
    """Complete daily bars that closed before ``day`` (UTC), oldest first."""
    end_ms = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.UTC).timestamp() * 1000) - 1
    return binance.daily_klines(symbol, limit=n, end_ms=end_ms)


def _mark(journal: Journal, day: dt.date, symbols: list[str], late: bool) -> dict[str, Any]:
    prices: dict[str, float] = {}
    bars: dict[str, int] = {}
    for s in symbols:
        rows = _bars(s, day, 3)
        if not rows:
            raise RunError(f"no complete daily bar for {s} before {day}")
        bars[s], prices[s] = rows[-1][0], rows[-1][1]
    return journal.append("mark", {"day": day.isoformat(), "prices": prices, "bar_open_ms": bars, "late": late})


def _peak_drawdown(journal: Journal) -> float:
    """Drawdown of the paper book from its running peak at the last mark (0.0 before the first mark)."""
    marks = account.replay(journal.entries(), "paper")["marks"]
    if not marks:
        return 0.0
    return float(marks[-1]["nav"] / max(m["nav"] for m in marks) - 1.0)


def _trade(journal: Journal, ex: Any, cfg: dict[str, Any], book: str, day: dt.date, symbol: str, delta_qty: float, mainnet_px: float) -> None:
    side = "BUY" if delta_qty > 0 else "SELL"
    qty = abs(delta_qty)
    cost = cfg["cost_model"]
    d = day.isoformat()
    if book == "paper":
        slip = cost["slippage_bps"] / 1e4
        px = mainnet_px * (1 + slip if side == "BUY" else 1 - slip)
        journal.append("paper_fill", {"day": d, "symbol": symbol, "side": side, "qty": qty, "price": px,
                                      "fee_usdt": qty * px * cost["fee_bps"] / 1e4, "mainnet_price": mainnet_px})
        return
    f = ex.filters(symbol)
    qty = binance.round_step(qty, f["step"])
    if qty < f["min_qty"] or qty * mainnet_px < f["min_notional"]:
        if not journal.find("skip", day=d, symbol=symbol, side=side) and not journal.find("order", day=d, symbol=symbol):  # a residual after a filled order is rounding, not a skip
            journal.append("skip", {"day": d, "symbol": symbol, "side": side, "qty": qty, "why": "below exchange minimum"})
        return
    if isinstance(ex, binance.SimExchange):  # a dry run fills at the price of the day it replays, not at today's price
        ex.prices = {**(ex.prices or {}), symbol: mainnet_px}
    cid = binance.client_order_id(d, symbol, side, journal.find("start")[0]["hash"])
    if not journal.find("order", client_order_id=cid):
        journal.append("order", {"day": d, "symbol": symbol, "side": side, "qty": qty, "client_order_id": cid})
    o = ex.market_order(symbol, side, qty, cid)
    if journal.find("fill", client_order_id=cid):  # fills of this order are already recorded (resumed run)
        return
    px_now = mainnet_px if isinstance(ex, binance.SimExchange) else binance.mainnet_price(symbol)
    base = symbol[:-4]
    for fl in o.get("fills", []):
        fee = float(fl["commission"])
        asset = fl["commissionAsset"]
        fee_usdt = fee if asset == "USDT" else fee * float(fl["price"]) if asset == base else 0.0
        journal.append("fill", {"day": d, "symbol": symbol, "side": side, "qty": float(fl["qty"]), "price": float(fl["price"]),
                                "fee_usdt": fee_usdt, "commission": fee, "commission_asset": asset,
                                "client_order_id": cid, "mainnet_price_at_fill": px_now, "status": o.get("status")})


def _rebalance(journal: Journal, ex: Any, cfg: dict[str, Any], fn: plugin.WeightsFn, day: dt.date, late: bool) -> None:
    symbols, books = cfg["symbols"], books_for(cfg["mode"])
    closes = {s: [c for _, c in _bars(s, day, cfg.get("lookback", LOOKBACK))] for s in symbols}
    px = {s: c[-1] for s, c in closes.items()}
    prior = journal.find("signal", day=day.isoformat())
    if prior:  # a resumed rebalance reuses the recorded decision and NAVs instead of asking the plug-in again
        weights, navs = prior[0]["body"]["weights"], prior[0]["body"]["nav_before"]
    else:
        weights = plugin.call(fn, closes, symbols)
        navs = {b: account.nav(account.replay(journal.entries(), b), px) for b in books}
        digest = hashlib.sha256(json.dumps(closes, sort_keys=True).encode()).hexdigest()
        journal.append("signal", {"day": day.isoformat(), "weights": weights, "inputs_sha256": digest, "nav_before": navs,
                                  "strategy_sha256": cfg["strategy"]["sha256"], "last_bar_close": px})
    for book in books:
        acc = account.replay(journal.entries(), book)
        deltas = {s: weights[s] * navs[book] / px[s] - acc["positions"].get(s, 0.0) for s in symbols}
        for s in sorted(symbols, key=lambda k: deltas[k]):  # sells first, so cash is there for the buys
            if abs(deltas[s]) * px[s] > 1e-6:
                _trade(journal, ex, cfg, book, day, s, deltas[s], px[s])
    journal.append("rebalanced", {"day": day.isoformat(), "books": books, "late": late})


def _kill(journal: Journal, ex: Any, cfg: dict[str, Any], day: dt.date, dd: float) -> None:
    symbols = cfg["symbols"]
    px = {s: _bars(s, day, 3)[-1][1] for s in symbols}
    for book in books_for(cfg["mode"]):
        acc = account.replay(journal.entries(), book)
        for s, q in acc["positions"].items():
            if q > 0:
                _trade(journal, ex, cfg, book, day, s, -q, px[s])
    journal.append("kill", {"day": day.isoformat(), "drawdown": dd, "threshold": cfg["kill_drawdown"]})


def run_day(journal: Journal, ex: Any, fn: plugin.WeightsFn, day: dt.date | None = None, late: bool = False) -> dict[str, Any]:
    day = day or utc_today()
    cfg = config(journal)
    if day.isoformat() < cfg["first_day"]:
        return {"day": day.isoformat(), "done": [], "note": "before the first forward day"}
    done: list[str] = []
    if journal.find("kill"):
        if not journal.find("mark", day=day.isoformat()):
            _mark(journal, day, cfg["symbols"], late)
            done.append("mark")
        return {"day": day.isoformat(), "done": done, "note": "kill switch active: no trading"}
    if not journal.find("mark", day=day.isoformat()):
        _mark(journal, day, cfg["symbols"], late)
        done.append("mark")
    dd = _peak_drawdown(journal)
    if dd <= cfg["kill_drawdown"]:
        _kill(journal, ex, cfg, day, dd)
        return {"day": day.isoformat(), "done": [*done, "kill"], "drawdown": dd}
    if is_rebalance_day(cfg, day) and not journal.find("rebalanced", day=day.isoformat()):
        _rebalance(journal, ex, cfg, fn, day, late)
        done.append("rebalance")
    return {"day": day.isoformat(), "done": done, "drawdown": dd}


def catch_up(journal: Journal, ex: Any, fn: plugin.WeightsFn, today: dt.date | None = None) -> list[dict[str, Any]]:
    """Run every day from the first forward day (or the last marked day, whose unfinished steps are completed) to ``today``; missed days are marked late."""
    today = today or utc_today()
    cfg = config(journal)
    marks = journal.find("mark")
    d = dt.date.fromisoformat(marks[-1]["body"]["day"]) if marks else dt.date.fromisoformat(cfg["first_day"])
    out = []
    while d <= today:
        out.append(run_day(journal, ex, fn, d, late=d < today))
        d += dt.timedelta(days=1)
    return out
