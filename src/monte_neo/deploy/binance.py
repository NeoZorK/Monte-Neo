"""Binance REST: public mainnet data (signals) and the signed spot testnet (execution). Standard library only.

Keys are passed in by the caller (see :mod:`monte_neo.deploy.keys`); they are never logged or written. Orders carry a
deterministic ``newClientOrderId`` and the order is looked up BEFORE it is sent, so a retry after a network error never
sends it twice. :class:`SimExchange` has the same interface for dry runs: it fills at the price of the day it replays.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MAINNET = "https://api.binance.com"  # public market data only: no key is ever sent here
SPOT_TESTNET = "https://testnet.binance.vision"  # the only host that receives signed requests
UA = "monte-neo-deploy/1"


class ExchangeError(RuntimeError):
    """A failed exchange call (the message never contains key material)."""


def _get_json(url: str, headers: dict[str, str] | None = None, method: str = "GET", data: bytes | None = None, tries: int = 5) -> Any:
    if not url.startswith("https://"):  # Binance REST only, over HTTPS
        raise ValueError(f"refusing a non-HTTPS URL: {url}")
    last: Exception | None = None
    for attempt in range(tries):
        req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": UA, **(headers or {})})  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310  # nosec B310 - scheme checked above
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            if e.code in (400, 401, 403, 404):  # a client error does not get better with a retry
                raise ExchangeError(f"HTTP {e.code}: {body}") from None
            last = ExchangeError(f"HTTP {e.code}: {body}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(min(30, 2**attempt))
    raise ExchangeError(f"giving up after {tries} tries: {last}")


def daily_klines(symbol: str, limit: int = 500, end_ms: int | None = None) -> list[tuple[int, float]]:
    """(open time ms, close) of COMPLETE mainnet daily bars, oldest first (the bar still forming is dropped)."""
    q: dict[str, Any] = {"symbol": symbol, "interval": "1d", "limit": limit}
    if end_ms is not None:
        q["endTime"] = end_ms
    rows = _get_json(f"{MAINNET}/api/v3/klines?{urllib.parse.urlencode(q)}")
    now_ms = int(time.time() * 1000)
    return [(int(r[0]), float(r[4])) for r in rows if int(r[6]) < now_ms]


def mainnet_price(symbol: str) -> float:
    return float(_get_json(f"{MAINNET}/api/v3/ticker/price?symbol={symbol}")["price"])


def round_step(qty: float, step: float) -> float:
    """Round a quantity DOWN to the exchange step (never sends more than intended)."""
    if step <= 0:
        return qty
    n = math.floor(qty / step + 1e-9)
    decimals = max(0, -int(math.floor(math.log10(step)))) if step < 1 else 0
    return round(n * step, decimals)


def client_order_id(day: str, symbol: str, side: str, run: str = "") -> str:
    """Deterministic id (<= 36 chars): the same run, day, symbol and side always give the same id.

    ``run`` (the hash of the run's start entry) keeps two strategies on one account from ever sharing an id: a resumed
    order of one run must never be taken for an order of another.
    """
    return "nmd" + hashlib.sha256(f"{run}|{day}|{symbol}|{side}".encode()).hexdigest()[:29]


class SpotTestnet:
    """Signed spot testnet client (demo money only)."""

    def __init__(self, base: str = SPOT_TESTNET, key: str | None = None, secret: str | None = None) -> None:
        self.base = base
        self.key = key or os.environ.get("MONTE_NEO_TESTNET_KEY", "")
        self.secret = (secret or os.environ.get("MONTE_NEO_TESTNET_SECRET", "")).encode()
        if not self.key or not self.secret:
            raise ExchangeError("no testnet keys: set MONTE_NEO_TESTNET_KEY and MONTE_NEO_TESTNET_SECRET, or store them in the Keychain (monte-neo deploy keys)")
        self._filters: dict[str, dict[str, float]] = {}

    def __repr__(self) -> str:  # never show key material
        return f"SpotTestnet(base={self.base!r})"

    def _signed(self, method: str, path: str, params: dict[str, Any]) -> Any:
        p = {**params, "timestamp": int(time.time() * 1000), "recvWindow": 10000}
        qs = urllib.parse.urlencode(p)
        sig = hmac.new(self.secret, qs.encode(), hashlib.sha256).hexdigest()
        url = f"{self.base}{path}?{qs}&signature={sig}"
        return _get_json(url, headers={"X-MBX-APIKEY": self.key}, method=method, tries=1 if method == "POST" else 5)

    def filters(self, symbol: str) -> dict[str, float]:
        if symbol not in self._filters:
            info = _get_json(f"{self.base}/api/v3/exchangeInfo?symbol={symbol}")["symbols"][0]
            f = {x["filterType"]: x for x in info["filters"]}
            notional = f.get("NOTIONAL") or f.get("MIN_NOTIONAL") or {}
            self._filters[symbol] = {"step": float(f["LOT_SIZE"]["stepSize"]), "min_qty": float(f["LOT_SIZE"]["minQty"]),
                                     "min_notional": float(notional.get("minNotional", 0) or 0)}
        return self._filters[symbol]

    def balances(self) -> dict[str, float]:
        acc = self._signed("GET", "/api/v3/account", {"omitZeroBalances": "true"})
        return {b["asset"]: float(b["free"]) + float(b["locked"]) for b in acc["balances"]}

    def find_order(self, symbol: str, cid: str) -> dict[str, Any] | None:
        try:
            return self._signed("GET", "/api/v3/order", {"symbol": symbol, "origClientOrderId": cid})  # type: ignore[no-any-return]
        except ExchangeError as e:
            if "-2013" in str(e):  # order does not exist
                return None
            raise

    def market_order(self, symbol: str, side: str, qty: float, cid: str) -> dict[str, Any]:
        """Send a market order once: an order with this client id that already exists is returned, never sent again
        (Binance keeps client ids unique only among OPEN orders, so a filled one could otherwise be duplicated)."""
        existing = self.find_order(symbol, cid)
        if existing is not None:
            return self._with_fills(existing)
        try:
            return self._signed("POST", "/api/v3/order", {"symbol": symbol, "side": side, "type": "MARKET",
                                                           "quantity": f"{qty:.8f}".rstrip("0").rstrip("."),
                                                           "newClientOrderId": cid, "newOrderRespType": "FULL"})  # type: ignore[no-any-return]
        except ExchangeError:
            found = self.find_order(symbol, cid)  # the POST may have gone through before the error
            if found is None:
                raise
            return self._with_fills(found)

    def _with_fills(self, order: dict[str, Any]) -> dict[str, Any]:
        """An order looked up by id has no fills: add them from the account's trades of that order."""
        if order.get("fills"):
            return order
        trades = self._signed("GET", "/api/v3/myTrades", {"symbol": order["symbol"], "orderId": order["orderId"]})
        order["fills"] = [{"price": t["price"], "qty": t["qty"], "commission": t["commission"], "commissionAsset": t["commissionAsset"]}
                          for t in trades]
        return order


class SimExchange:
    """Dry-run exchange: fills at the price of the day being replayed plus fixed slippage; balances live in memory."""

    def __init__(self, cash: float = 10_000.0, slippage_bps: float = 5.0, fee_bps: float = 10.0, prices: dict[str, float] | None = None) -> None:
        self.bal: dict[str, float] = {"USDT": cash}
        self.slip, self.fee, self.prices = slippage_bps / 1e4, fee_bps / 1e4, prices
        self.orders: dict[str, dict[str, Any]] = {}

    def filters(self, symbol: str) -> dict[str, float]:
        return {"step": 1e-5, "min_qty": 1e-5, "min_notional": 5.0}

    def balances(self) -> dict[str, float]:
        return {k: v for k, v in self.bal.items() if abs(v) > 0}

    def find_order(self, symbol: str, cid: str) -> dict[str, Any] | None:
        return self.orders.get(cid)

    def market_order(self, symbol: str, side: str, qty: float, cid: str) -> dict[str, Any]:
        if cid in self.orders:
            return self.orders[cid]
        px = (self.prices or {}).get(symbol) or mainnet_price(symbol)
        fill = px * (1 + self.slip if side == "BUY" else 1 - self.slip)
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        notional = fill * qty
        fee = notional * self.fee
        sign = 1 if side == "BUY" else -1
        self.bal[base] = self.bal.get(base, 0.0) + sign * qty
        self.bal["USDT"] = self.bal.get("USDT", 0.0) - sign * notional - fee
        o = {"symbol": symbol, "side": side, "status": "FILLED", "clientOrderId": cid, "executedQty": str(qty),
             "cummulativeQuoteQty": str(notional),
             "fills": [{"price": str(fill), "qty": str(qty), "commission": str(fee), "commissionAsset": "USDT"}]}
        self.orders[cid] = o
        return o
