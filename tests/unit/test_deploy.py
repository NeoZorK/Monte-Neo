"""``monte-neo deploy``: journal, plug-in contract, eligibility, an idempotent dry run, costs, report and keys (offline)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from monte_neo.cli import deploy_cmd
from monte_neo.deploy import account, anchor, binance, dashboard, keys, metrics, plugin, report, runner
from monte_neo.deploy import journal as jr
from monte_neo.deploy.eligibility import EligibilityError, check_certificate, check_settings

STRATEGY = '''
def target_weights(closes_by_symbol):
    out = {}
    for s, c in closes_by_symbol.items():
        out[s] = 0.4 if len(c) >= 5 and c[-1] > sum(c[-5:]) / 5 else 0.0
    return out
'''
BASE = {"BTCUSDT": 30_000.0, "ETHUSDT": 2_000.0}


def _price(symbol: str, day: dt.date) -> float:
    k = day.toordinal()
    phase = 0.0 if symbol == "BTCUSDT" else 1.3
    return BASE[symbol] * (1.0 + 0.04 * math.sin(k / 2.7 + phase) + 0.0008 * (k % 50))


@pytest.fixture(autouse=True)
def fake_market(monkeypatch: pytest.MonkeyPatch) -> None:
    def klines(symbol: str, limit: int = 500, end_ms: int | None = None) -> list[tuple[int, float]]:
        last = dt.datetime.fromtimestamp((end_ms or 0) / 1000, dt.UTC).date()
        days = [last - dt.timedelta(days=i) for i in range(limit - 1, -1, -1)]
        return [(int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC).timestamp() * 1000), _price(symbol, d)) for d in days]

    monkeypatch.setattr(binance, "daily_klines", klines)
    monkeypatch.setattr(binance, "mainnet_price", lambda s: BASE[s])


def _cert(path: Path, strategy: Path, verdict: str = "PASS", source: bool = True) -> Path:
    repro: dict[str, Any] = {"n_trials": 7}
    if source:
        repro["source_sha256"] = hashlib.sha256(strategy.read_text().encode()).hexdigest()
    path.write_text(json.dumps({"verdict": verdict, "certificate_id": "cert-abc", "arl": {"level": 2, "headline": "ARL 2"}, "reproducibility": repro}))
    return path


def _init(tmp_path: Path, *extra: str, verdict: str = "PASS", source: bool = True) -> tuple[list[str], Path]:
    strat = tmp_path / "s.py"
    strat.write_text(STRATEGY)
    cert = _cert(tmp_path / "cert.json", strat, verdict, source)
    common = ["--var", str(tmp_path / "var"), "--run", "r"]
    code = deploy_cmd.main(["init", *common, "--strategy", str(strat), "--certificate", str(cert), "--mode", "dry", "--first-day", "2026-10-05", *extra])
    assert code == 0
    return common, tmp_path / "var" / "r"


def _entries(folder: Path) -> list[dict[str, Any]]:
    return list(jr.Journal(folder / "journal.jsonl").entries())


# ------------------------------------------------------------------ journal
def test_journal_chain_tamper_and_tail_repair(tmp_path: Path) -> None:
    j = jr.Journal(tmp_path / "j.jsonl")
    for i in range(4):
        j.append("mark", {"day": f"d{i}", "x": i})
    assert jr.verify(j.path)["ok"] and jr.verify(j.path)["entries"] == 4
    good = j.path.read_text()
    j.path.write_text(good.replace('"x":1', '"x":9'))  # edit one body
    bad = jr.verify(j.path)
    assert not bad["ok"] and "line 2" in bad["problem"]
    lines = good.splitlines()
    j.path.write_text("\n".join([lines[0], lines[2], lines[1], lines[3]]) + "\n")  # reorder
    assert not jr.verify(j.path)["ok"]
    j.path.write_text(good + '{"seq": 4, "ts": "x", "kin')  # power cut mid-write
    assert not jr.verify(j.path)["ok"]
    aside = j.repair_tail()
    assert aside is not None and aside.exists()
    assert jr.verify(j.path)["ok"] and j.head()["seq"] == 3
    assert j.append("mark", {"day": "d4"})["seq"] == 4 and jr.verify(j.path)["ok"]


# ------------------------------------------------------------------ plug-in contract
@pytest.mark.parametrize("bad", [[1, 2], {"XRPUSDT": 0.1}, {"BTCUSDT": -0.1}, {"BTCUSDT": 1.5}, {"BTCUSDT": 0.7, "ETHUSDT": 0.5},
                                 {"BTCUSDT": float("nan")}, {"BTCUSDT": True}, {"BTCUSDT": "0.5"}, None])
def test_plugin_rejects_bad_weights(bad: Any) -> None:
    with pytest.raises(plugin.PluginError):
        plugin.validate(bad, ["BTCUSDT", "ETHUSDT"])


def test_plugin_accepts_and_fills_missing(tmp_path: Path) -> None:
    assert plugin.validate({"BTCUSDT": 0.5}, ["BTCUSDT", "ETHUSDT"]) == {"BTCUSDT": 0.5, "ETHUSDT": 0.0}
    f = tmp_path / "s.py"
    f.write_text(STRATEGY)
    fn = plugin.load(f)
    assert plugin.call(fn, {"BTCUSDT": [1.0, 1, 1, 1, 2.0], "ETHUSDT": [1.0] * 5}, ["BTCUSDT", "ETHUSDT"]) == {"BTCUSDT": 0.4, "ETHUSDT": 0.0}


def test_plugin_load_and_runtime_errors(tmp_path: Path) -> None:
    f = tmp_path / "no.py"
    f.write_text("x = 1\n")
    with pytest.raises(plugin.PluginError, match="target_weights"):
        plugin.load(f)
    with pytest.raises(plugin.PluginError, match="not found"):
        plugin.load(tmp_path / "missing.py")
    def boom(c: dict[str, list[float]]) -> dict[str, float]:
        raise KeyError("x")
    with pytest.raises(plugin.PluginError, match="raised KeyError"):
        plugin.call(boom, {"BTCUSDT": [1.0]}, ["BTCUSDT"])


# ------------------------------------------------------------------ eligibility
def test_reject_certificate_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    strat = tmp_path / "s.py"
    strat.write_text(STRATEGY)
    cert = _cert(tmp_path / "c.json", strat, verdict="REJECT")
    code = deploy_cmd.main(["init", "--var", str(tmp_path / "v"), "--strategy", str(strat), "--certificate", str(cert), "--mode", "dry"])
    assert code == 3 and "REJECT" in capsys.readouterr().err
    assert not (tmp_path / "v" / "default" / "journal.jsonl").exists()


def test_certificate_source_hash_must_match_or_warn(tmp_path: Path) -> None:
    strat = tmp_path / "s.py"
    strat.write_text(STRATEGY)
    cert = _cert(tmp_path / "c.json", strat)
    strat.write_text(STRATEGY + "\n# edited\n")
    with pytest.raises(EligibilityError, match="does not match"):
        check_certificate(cert, strat)
    cert2 = _cert(tmp_path / "c2.json", strat, source=False)
    out = check_certificate(cert2, strat)
    assert out["warnings"] and out["certificate"]["id"] == "cert-abc"


def test_init_records_eligibility_and_warning(tmp_path: Path) -> None:
    _, folder = _init(tmp_path, source=False)
    start = _entries(folder)[0]["body"]
    assert start["certificate"]["id"] == "cert-abc" and start["certificate"]["verdict"] == "PASS" and start["certificate"]["arl"] == 2
    assert start["strategy"]["sha256"] == hashlib.sha256(STRATEGY.encode()).hexdigest()
    assert start["warnings"] and start["target"] == "local" and start["weekday"] == 0 and start["kill_drawdown"] == -0.15


def test_unsupported_settings_and_targets(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for kw in ({"market": "futures"}, {"leverage": 2.0}, {"rebalance": "hourly"}, {"symbols": ["BTCUSD"]}, {"kill_drawdown": 0.1}):
        with pytest.raises(EligibilityError):
            check_settings(**{"symbols": ["BTCUSDT"], **kw})
    for t in ("ssh", "aws", "gcp"):
        assert deploy_cmd.main(["status", "--target", t, "--var", str(tmp_path)]) == 2
        assert "not available yet" in capsys.readouterr().err
    assert deploy_cmd.main(["status", "--target", "mars", "--var", str(tmp_path)]) == 3


# ------------------------------------------------------------------ dry run over three weeks
def test_dry_run_three_weeks_is_idempotent_and_reconciles(tmp_path: Path) -> None:
    common, folder = _init(tmp_path)
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-25"]) == 0
    first = _entries(folder)
    kinds = [e["kind"] for e in first]
    assert kinds.count("mark") == 21 and kinds.count("rebalanced") == 3 and kinds.count("signal") == 3
    assert kinds.count("paper_fill") > 0 and kinds.count("fill") == kinds.count("order") > 0
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-25"]) == 0
    assert _entries(folder) == first  # a second run adds nothing
    assert jr.verify(folder / "journal.jsonl")["ok"]
    # books: the simulated exchange fills like the paper book, so both books and the returns agree
    paper, test = account.replay(first, "paper"), account.replay(first, "testnet")
    assert paper["positions"].keys() == test["positions"].keys()
    for s, q in paper["positions"].items():
        assert q == pytest.approx(test["positions"][s], rel=1e-5, abs=1e-4)
    assert paper["cash"] == pytest.approx(test["cash"], rel=1e-4)
    assert metrics.tracking_error(account.daily_returns(paper["marks"]), account.daily_returns(test["marks"])) == pytest.approx(0.0, abs=1e-3)
    assert (folder / "site" / "index.html").exists()
    assert deploy_cmd.main(["verify", *common]) == 0
    assert deploy_cmd.main(["status", *common]) == 0


def test_resume_after_partial_rebalance_does_not_duplicate(tmp_path: Path) -> None:
    common, folder = _init(tmp_path)
    j = jr.Journal(folder / "journal.jsonl")
    cfg = runner.config(j)
    fn = plugin.load(folder / "strategy.py")
    ex = binance.SimExchange(cash=cfg["capital"])
    runner.run_day(j, ex, fn, dt.date(2026, 10, 5))
    n = len(list(j.entries()))
    # a crash after the signal but before "rebalanced": drop that last entry, run again with a fresh exchange
    lines = j.path.read_text().splitlines()
    assert json.loads(lines[-1])["kind"] == "rebalanced"
    j.path.write_text("\n".join(lines[:-1]) + "\n")
    runner.run_day(j, binance.SimExchange(cash=cfg["capital"]), fn, dt.date(2026, 10, 5))
    entries = list(j.entries())
    assert len(entries) == n
    assert len([e for e in entries if e["kind"] == "signal"]) == 1


def test_kill_switch_stops_trading(tmp_path: Path) -> None:
    common, folder = _init(tmp_path, "--kill-drawdown", "-0.0001", "--rebalance", "daily")
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-20"]) == 0
    es = _entries(folder)
    kills = [i for i, e in enumerate(es) if e["kind"] == "kill"]
    assert len(kills) == 1
    assert not any(e["kind"] in ("paper_fill", "fill") for e in es[kills[0] + 1:])
    assert account.replay(es, "paper")["positions"] == {k: 0.0 for k in account.replay(es, "paper")["positions"]}


def test_strategy_change_after_start_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    common, folder = _init(tmp_path)
    (folder / "strategy.py").write_text(STRATEGY + "\n# tampered\n")
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-06"]) == 3
    assert "no longer matches" in capsys.readouterr().err
    assert deploy_cmd.main(["verify", *common]) == 1


# ------------------------------------------------------------------ costs and metrics
def test_doubled_cost_returns_are_lower(tmp_path: Path) -> None:
    common, folder = _init(tmp_path, "--rebalance", "daily")
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-25"]) == 0
    es = _entries(folder)
    base = account.daily_returns(account.replay(es, "paper")["marks"])
    x2 = metrics.costs_x2_returns(es)
    assert len(base) == len(x2) and sum(x2) < sum(base)
    extra = sum(e["body"]["fee_usdt"] + abs(e["body"]["price"] - e["body"]["mainnet_price"]) * e["body"]["qty"] for e in es if e["kind"] == "paper_fill")
    assert extra > 0
    s = metrics.summary(es)
    assert s["sharpe_costs_x2"] is not None and s["sharpe_costs_x2"] < s["sharpe"]


def test_metric_helpers() -> None:
    assert metrics.max_drawdown([100, 120, 90, 130]) == pytest.approx(-0.25)
    assert metrics.worst_week([100.0] * 7 + [90.0]) == pytest.approx(-0.10)
    assert metrics.var_es([0.01] * 30 + [-0.05, -0.04])["es"] < metrics.var_es([0.01] * 30 + [-0.05, -0.04])["var"] + 1e-12
    assert metrics.sharpe([0.01]) is None


# ------------------------------------------------------------------ report
def test_report_manifest_verify_and_stress(tmp_path: Path) -> None:
    common, folder = _init(tmp_path)
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-25"]) == 0
    jpath, out = folder / "journal.jsonl", folder / "report"
    built = report.build(jpath, out, {"Window": ("2026-09-01", "2026-09-30")}, folder / "strategy.py")
    assert (out / "report.html").exists() and built["sha256"]
    manifest = json.loads((out / "report_manifest.json").read_text())
    assert manifest["numbers"]["stress"]["Window"]["days"] > 0
    assert report.verify(jpath, out, folder / "strategy.py")["ok"]
    manifest["numbers"]["summary"]["paper_return"] = 9.99  # edited number
    (out / "report_manifest.json").write_text(json.dumps(manifest))
    res = report.verify(jpath, out, folder / "strategy.py")
    assert not res["ok"] and "summary" in res["differs"]
    assert report.parse_window("A b=2020-01-01:2020-02-01") == ("A b", ("2020-01-01", "2020-02-01"))
    with pytest.raises(ValueError):
        report.parse_window("bad")


def test_report_no_stress_and_dashboard(tmp_path: Path) -> None:
    common, folder = _init(tmp_path)
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-12"]) == 0
    assert deploy_cmd.main(["report", *common, "--no-stress"]) == 0
    assert deploy_cmd.main(["report", *common, "--verify"]) == 0
    page = (folder / "site" / "index.html").read_text()
    assert "<script" not in page.lower() and "http://" not in page and "https://" not in page and "<svg" in page
    assert "cert-abc" in page and "chain intact" in page


def test_certify_in_process(tmp_path: Path) -> None:
    common, folder = _init(tmp_path, "--rebalance", "daily")
    assert deploy_cmd.main(["run", *common, "--until", "2026-11-20"]) == 0
    assert deploy_cmd.main(["certify", *common]) == 0
    c = jr.Journal(folder / "journal.jsonl").find("certify")[0]["body"]
    assert c["n_strategies"] == 7 and c["verdict"] in ("PASS", "PASS_WITH_WARNINGS", "NEEDS_MORE_EVIDENCE", "REJECT") and c["certificate_id"]
    assert (folder / "certify" / "certificate.json").exists()


def test_certify_too_short_is_an_input_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    common, _ = _init(tmp_path)
    assert deploy_cmd.main(["run", *common, "--until", "2026-10-08"]) == 0
    assert deploy_cmd.main(["certify", *common]) == 3
    assert "cannot certify" in capsys.readouterr().err


# ------------------------------------------------------------------ exchange client, anchors, server
def test_testnet_order_is_looked_up_before_sending() -> None:
    ex = binance.SpotTestnet(key="K" * 40, secret="S" * 40)
    calls: list[tuple[str, str]] = []
    existing = {"symbol": "BTCUSDT", "orderId": 7, "status": "FILLED"}

    def signed(method: str, path: str, params: dict[str, Any]) -> Any:
        calls.append((method, path))
        if path == "/api/v3/order" and method == "GET":
            return existing
        if path == "/api/v3/myTrades":
            return [{"price": "30000", "qty": "0.1", "commission": "3", "commissionAsset": "USDT"}]
        raise AssertionError("an existing order must not be sent again")

    ex._signed = signed  # type: ignore[method-assign]
    o = ex.market_order("BTCUSDT", "BUY", 0.1, binance.client_order_id("2026-10-05", "BTCUSDT", "BUY"))
    assert calls == [("GET", "/api/v3/order"), ("GET", "/api/v3/myTrades")]
    assert o["fills"][0]["qty"] == "0.1"
    assert binance.client_order_id("d", "BTCUSDT", "BUY") == binance.client_order_id("d", "BTCUSDT", "BUY")
    assert len(binance.client_order_id("d", "BTCUSDT", "BUY")) <= 36
    assert binance.round_step(0.123456, 0.001) == 0.123
    assert "K" * 10 not in repr(ex)


def test_anchor_falls_back_to_next_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    j = jr.Journal(tmp_path / "j.jsonl")
    j.append("mark", {"day": "d"})
    monkeypatch.setattr(anchor, "make_query", lambda text, tsq: tsq.write_bytes(b"query"))
    tried: list[str] = []

    def post(tsa: str, data: bytes) -> bytes:
        tried.append(tsa)
        if "freetsa" in tsa:
            raise OSError("down")
        return b"reply"

    monkeypatch.setattr(anchor, "post", post)
    body = anchor.anchor(j, tmp_path / "anchors")
    assert tried[0].startswith("https://freetsa.org") and "digicert" in body["tsa"] and len(tried) == 2
    assert "skipped" in anchor.anchor(j, tmp_path / "anchors")  # one per day
    assert len(j.find("anchor")) == 1


def test_dashboard_server_is_read_only(tmp_path: Path) -> None:
    import threading
    import urllib.error
    import urllib.request

    (tmp_path / "index.html").write_text("<p>ok</p>")
    srv = dashboard.make_server(tmp_path, "127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        assert urllib.request.urlopen(f"http://127.0.0.1:{port}/").read() == b"<p>ok</p>"  # noqa: S310
        req = urllib.request.Request(f"http://127.0.0.1:{port}/", data=b"x", method="POST")  # noqa: S310
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req)  # noqa: S310
        assert err.value.code == 405
    finally:
        srv.shutdown()
        srv.server_close()


# ------------------------------------------------------------------ keys are never printed
def test_keys_never_printed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    secret_key, secret_val = "A1b2C3d4" * 5, "Z9y8X7w6" * 5
    monkeypatch.setenv(keys.ENV_KEY, secret_key)
    monkeypatch.setenv(keys.ENV_SECRET, secret_val)
    monkeypatch.setattr(keys, "check_pair", lambda k, s: (False, "the spot testnet does not accept this pair (a mainnet key is never used)"))
    assert deploy_cmd.main(["keys", "--status"]) == 0
    # discovery in a file: names and paths are shown, values are not
    env = tmp_path / ".env"
    env.write_text(f"BINANCE_API_KEY={secret_key}\nBINANCE_API_SECRET={secret_val}\n")
    monkeypatch.setattr(keys, "PLACES", [str(tmp_path)])
    assert deploy_cmd.main(["keys", "--list"]) == 0
    stored: list[tuple[str, str]] = []
    monkeypatch.setattr(keys, "store", lambda k, s: stored.append((k, s)))
    assert deploy_cmd.main(["keys", "--yes"]) == 0
    assert not stored  # a pair the testnet rejects is never stored
    out = capsys.readouterr()
    assert secret_key not in out.out + out.err and secret_val not in out.out + out.err
    assert ".env" in out.out
    monkeypatch.delenv(keys.ENV_KEY)
    monkeypatch.delenv(keys.ENV_SECRET)
    with pytest.raises(binance.ExchangeError) as exc:
        binance.SpotTestnet(key="", secret="")
    assert secret_key not in str(exc.value)


def test_keys_resolve_prefers_env_and_checks_only_testnet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(keys.ENV_KEY, "k" * 40)
    monkeypatch.setenv(keys.ENV_SECRET, "s" * 40)
    assert keys.resolve() == ("k" * 40, "s" * 40, "env")
    hosts: list[str] = []

    def fake_signed(self: binance.SpotTestnet, method: str, path: str, params: dict[str, Any]) -> Any:
        hosts.append(self.base)
        raise binance.ExchangeError("HTTP 401")

    monkeypatch.setattr(binance.SpotTestnet, "_signed", fake_signed)
    ok, _ = keys.check_pair("k" * 40, "s" * 40)
    assert not ok and hosts == [binance.SPOT_TESTNET]
