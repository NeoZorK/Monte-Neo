"""Deploy connectors: the USD-M futures venue (shorts, gross limit, funding) and the futures testnet client (offline)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from monte_neo.cli import deploy_cmd
from monte_neo.deploy import account, binance, connectors, plugin, runner
from monte_neo.deploy.eligibility import EligibilityError, check_settings
from monte_neo.deploy.journal import Journal

NEUTRAL = '''
def target_weights(closes_by_symbol):
    b, e = closes_by_symbol["BTCUSDT"], closes_by_symbol["ETHUSDT"]
    rb, re_ = b[-1] / b[-6] - 1.0, e[-1] / e[-6] - 1.0
    return {"BTCUSDT": 0.5, "ETHUSDT": -0.5} if rb > re_ else {"BTCUSDT": -0.5, "ETHUSDT": 0.5}
'''
BASE = {"BTCUSDT": 30_000.0, "ETHUSDT": 2_000.0}
RATE = 0.0001  # per funding event, three a day


def _price(symbol: str, day: dt.date) -> float:
    k = day.toordinal()
    phase = 0.0 if symbol == "BTCUSDT" else 1.3
    return BASE[symbol] * (1.0 + 0.04 * math.sin(k / 2.7 + phase) + 0.0008 * (k % 50))


@pytest.fixture(autouse=True)
def fake_futures(monkeypatch: pytest.MonkeyPatch) -> None:
    def klines(symbol: str, limit: int = 500, end_ms: int | None = None) -> list[tuple[int, float]]:
        last = dt.datetime.fromtimestamp((end_ms or 0) / 1000, dt.UTC).date()
        days = [last - dt.timedelta(days=i) for i in range(limit - 1, -1, -1)]
        return [(int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC).timestamp() * 1000), _price(symbol, d)) for d in days]

    def funding(symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float, float | None]]:
        return [(start_ms + i * 8 * 3_600_000, RATE, None) for i in range(3)]

    def spot_called(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("a usdm run must not read spot prices")

    monkeypatch.setattr(binance, "futures_daily_klines", klines)
    monkeypatch.setattr(binance, "futures_price", lambda s: BASE[s])
    monkeypatch.setattr(binance, "funding_rates", funding)
    monkeypatch.setattr(binance, "daily_klines", spot_called)


def _init(tmp_path: Path, *extra: str, strategy: str = NEUTRAL) -> list[str]:
    strat = tmp_path / "s.py"
    strat.write_text(strategy)
    cert = tmp_path / "cert.json"
    cert.write_text(json.dumps({"verdict": "PASS", "certificate_id": "cert-mn", "arl": {"level": 2},
                                "reproducibility": {"n_trials": 3, "source_sha256": hashlib.sha256(strategy.encode()).hexdigest()}}))
    common = ["--var", str(tmp_path / "var"), "--run", "mn"]
    code = deploy_cmd.main(["init", *common, "--strategy", str(strat), "--certificate", str(cert), "--mode", "dry",
                            "--market", "usdm", "--rebalance", "daily", "--first-day", "2026-10-05", *extra])
    assert code == 0
    return common


def _journal(tmp_path: Path) -> Journal:
    return Journal(tmp_path / "var" / "mn" / "journal.jsonl")


def test_market_neutral_dry_run_holds_shorts_and_pays_funding(tmp_path: Path) -> None:
    common = _init(tmp_path)
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-12"]) == 0
    j = _journal(tmp_path)
    start = j.find("start")[0]["body"]
    assert start["venue"] == "binance_usdm" and start["max_gross"] == 1.0
    entries = list(j.entries())
    for book in ("paper", "testnet"):
        acc = account.replay(entries, book)
        assert any(q < 0 for q in acc["positions"].values()), book  # one leg is short
        assert len(acc["marks"]) == 8
    fund = [e["body"] for e in entries if e["kind"] == "funding"]
    assert fund and {f["book"] for f in fund} == {"paper", "testnet"}
    assert all(f["events"] == {"BTCUSDT": 3, "ETHUSDT": 3} for f in fund)
    assert len({(f["day"], f["book"]) for f in fund}) == len(fund)  # once per day and book
    # funding is paid by longs and received by shorts: with equal legs the net is close to zero but recorded per symbol
    f = fund[-1]
    signs = {s: math.copysign(1, a) for s, a in f["by_symbol"].items()}
    assert set(signs.values()) == {-1.0, 1.0}


def test_rerun_is_idempotent_with_funding(tmp_path: Path) -> None:
    common = _init(tmp_path)
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-09"]) == 0
    n = len(list(_journal(tmp_path).entries()))
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-09"]) == 0
    assert len(list(_journal(tmp_path).entries())) == n


def test_funding_changes_cash_of_its_book_only() -> None:
    entries = [{"kind": "start", "body": {"capital": 1000.0}},
               {"kind": "funding", "body": {"day": "2026-10-06", "book": "paper", "amount_usdt": -2.5}},
               {"kind": "funding", "body": {"day": "2026-10-06", "book": "testnet", "amount_usdt": 7.0}}]
    assert account.replay(entries, "paper")["cash"] == pytest.approx(997.5)
    assert account.replay(entries, "testnet")["cash"] == pytest.approx(1007.0)


def test_funding_payment_sign() -> None:
    ev = [(0, 0.001, 100.0)]
    assert connectors.funding_payment(2.0, ev, 0.0) == pytest.approx(-0.2)  # a long pays a positive rate
    assert connectors.funding_payment(-2.0, ev, 0.0) == pytest.approx(0.2)  # a short receives it
    assert connectors.funding_payment(1.0, [(0, 0.001, None)], 50.0) == pytest.approx(-0.05)  # fallback price


def test_kill_switch_closes_shorts(tmp_path: Path) -> None:
    common = _init(tmp_path, "--kill-drawdown", "-0.0001")
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-20"]) == 0
    j = _journal(tmp_path)
    assert j.find("kill")
    for book in ("paper", "testnet"):
        pos = account.replay(list(j.entries()), book)["positions"]
        assert all(abs(q) < 1e-6 for q in pos.values()), (book, pos)


def test_plugin_short_rules() -> None:
    syms = ["BTCUSDT", "ETHUSDT"]
    assert plugin.validate({"BTCUSDT": 0.5, "ETHUSDT": -0.5}, syms, allow_short=True) == {"BTCUSDT": 0.5, "ETHUSDT": -0.5}
    with pytest.raises(plugin.PluginError, match="long-only"):
        plugin.validate({"BTCUSDT": 0.5, "ETHUSDT": -0.5}, syms)
    with pytest.raises(plugin.PluginError, match="gross exposure"):
        plugin.validate({"BTCUSDT": 0.8, "ETHUSDT": -0.8}, syms, allow_short=True, max_gross=1.0)
    assert plugin.validate({"BTCUSDT": 0.8, "ETHUSDT": -0.8}, syms, allow_short=True, max_gross=2.0)["ETHUSDT"] == -0.8


def test_settings_by_venue() -> None:
    check_settings(market="usdm", leverage=2.0, long_only=False, symbols=["BTCUSDT"])
    with pytest.raises(EligibilityError, match="at most 2"):
        check_settings(market="usdm", leverage=3.0, long_only=False, symbols=["BTCUSDT"])
    with pytest.raises(EligibilityError, match="usdm"):
        check_settings(market="spot", long_only=False, symbols=["BTCUSDT"])
    with pytest.raises(EligibilityError, match="market must be"):
        check_settings(market="options", symbols=["BTCUSDT"])


def test_unknown_venue_points_to_compat() -> None:
    with pytest.raises(ValueError, match="catalog compat"):
        connectors.venue("bybit")
    assert connectors.venue({}).id == "binance_spot"  # runs started before connectors are spot
    assert connectors.venue("usdm").short


def test_testnet_mode_needs_the_venue_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="MONTE_NEO_FUTURES_TESTNET_KEY"):
        connectors.exchange(connectors.VENUES["binance_usdm"], "testnet", capital=1.0, fee_bps=0, slippage_bps=0, keys=None)
    ex = connectors.exchange(connectors.VENUES["binance_usdm"], "testnet", capital=1.0, fee_bps=0, slippage_bps=0, keys=("k" * 64, "s" * 64))
    assert isinstance(ex, binance.FuturesTestnet) and ex.base == binance.FUTURES_TESTNET
    assert "k" * 8 not in repr(ex)


def test_futures_testnet_order_is_looked_up_before_send_and_gets_fills(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    state: dict[str, Any] = {}

    def fake_signed(self: Any, method: str, path: str, params: dict[str, Any]) -> Any:
        calls.append((method, path))
        if path == "/fapi/v1/order" and method == "GET":
            if "order" not in state:
                raise binance.ExchangeError('HTTP 400: {"code":-2013,"msg":"Order does not exist."}')
            return state["order"]
        if path == "/fapi/v1/order" and method == "POST":
            assert params["side"] == "SELL" and params["newClientOrderId"] == "cid1"
            state["order"] = {"symbol": "ETHUSDT", "orderId": 7, "status": "FILLED", "clientOrderId": "cid1"}
            return dict(state["order"])
        if path == "/fapi/v1/userTrades":
            return [{"price": "2000.5", "qty": "0.25", "commission": "0.2", "commissionAsset": "USDT"}]
        raise AssertionError(path)

    monkeypatch.setattr(binance.FuturesTestnet, "_signed", fake_signed)
    ex = binance.FuturesTestnet(key="k" * 64, secret="s" * 64)
    o = ex.market_order("ETHUSDT", "SELL", 0.25, "cid1")
    assert o["fills"][0]["price"] == "2000.5"
    assert calls[:2] == [("GET", "/fapi/v1/order"), ("POST", "/fapi/v1/order")]
    calls.clear()
    ex.market_order("ETHUSDT", "SELL", 0.25, "cid1")  # a retry finds the order and never sends it again
    assert ("POST", "/fapi/v1/order") not in calls


def test_signed_hosts_are_testnets_only() -> None:
    assert all("testnet" in h for h in binance.SIGNED_HOSTS)
    assert all(v.signed_host in binance.SIGNED_HOSTS for v in connectors.VENUES.values())


def test_paper_book_matches_replay_by_hand(tmp_path: Path) -> None:
    common = _init(tmp_path)
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-07"]) == 0
    entries = list(_journal(tmp_path).entries())
    acc = account.replay(entries, "paper")
    fills = [e["body"] for e in entries if e["kind"] == "paper_fill"]
    fund = sum(e["body"]["amount_usdt"] for e in entries if e["kind"] == "funding" and e["body"]["book"] == "paper")
    cash = 10_000.0 - sum((1 if f["side"] == "BUY" else -1) * f["qty"] * f["price"] + f["fee_usdt"] for f in fills) + fund
    assert acc["cash"] == pytest.approx(cash)
    assert runner.books_for("dry") == ["paper", "testnet"]
