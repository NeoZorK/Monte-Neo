"""Stage 10: certificate history, pre-registration, hold-out oracle, portfolio, data doctor."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import tools_cmd
from monte_neo.mcp import tools as mcp
from monte_neo.verify import verify_strategy
from monte_neo.verify.chainlog import ChainLog
from monte_neo.verify.doctor import diagnose
from monte_neo.verify.history import History, diff_certificates, render_markdown
from monte_neo.verify.oracle import HoldoutOracle
from monte_neo.verify.portfolio import effective_number, verify_portfolio
from monte_neo.verify.register import Registry

DF = synthetic_ohlcv(1500, seed=4)
SMA = "import pandas as pd\n\n\ndef signal(df):\n    c = df['close']\n    return (c > c.rolling({n}).mean()).astype(int)\n"
LEAK = "def signal(df):\n    return (df['close'].shift(-2) > df['close']).astype(int)\n"


def _strategy(tmp_path: Path, name: str, source: str) -> str:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return str(path)


# ---- the chain ------------------------------------------------------------------------------------------------------


def test_the_chain_detects_edits_removals_and_refuses_to_extend_a_broken_file(tmp_path: Path) -> None:
    log = ChainLog(tmp_path / "x.jsonl")
    for i in range(3):
        log.append({"v": i})
    assert log.check() == {"ok": True, "entries": 3, "problem": None}
    lines = log.path.read_text().splitlines()
    log.path.write_text("\n".join([lines[0], lines[2]]) + "\n")  # entry 2 removed
    assert not log.check()["ok"]
    with pytest.raises(ValueError, match="not intact"):
        log.append({"v": 9})
    log.path.write_text("\n".join(lines).replace('"v": 1', '"v": 7') + "\n")
    assert not log.check()["ok"]


# ---- history ---------------------------------------------------------------------------------------------------------


def test_a_verdict_regression_is_found_and_flagged_in_the_diff_and_the_comment(tmp_path: Path) -> None:
    good = verify_strategy(DF, signal_fn=lambda d: (d["close"] > d["close"].rolling(20).mean()).astype(int))
    bad = verify_strategy(DF, signal_fn=lambda d: (d["close"].shift(-2) > d["close"]).astype(int))
    d = diff_certificates(good, bad)
    assert d["regression"] and "lookahead_truncation" in d["newly_failing"]
    ranks = {"verdict": "PASS", "checks": {"a": "pass"}, "metrics": {}, "certificate": "1", "n_trials": 1}
    worse = diff_certificates(ranks, {**ranks, "verdict": "NEEDS_MORE_EVIDENCE", "certificate": "2"})
    assert worse["verdict"]["worse"] and worse["regression"] and not worse["newly_failing"]
    assert not diff_certificates({**ranks, "verdict": "REJECT"}, ranks)["regression"]
    assert "regressed" in render_markdown(d) and "lookahead_truncation" in render_markdown(d)
    back = diff_certificates(bad, good)
    assert not back["regression"] and back["verdict"]["old"] == "REJECT"
    assert diff_certificates(good, good)["same_certificate"] and not diff_certificates(good, good)["checks"]


def test_history_cli_adds_checks_and_exits_2_on_a_regression(tmp_path: Path, capsys) -> None:
    good = verify_strategy(DF, signal_fn=lambda d: (d["close"] > d["close"].rolling(20).mean()).astype(int))
    bad = verify_strategy(DF, signal_fn=lambda d: (d["close"].shift(-2) > d["close"]).astype(int))
    (tmp_path / "good.json").write_text(json.dumps(good))
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    hist = str(tmp_path / "h.jsonl")
    assert tools_cmd.history_main(["add", str(tmp_path / "good.json"), "--label", "main", "--history", hist]) == 0
    assert tools_cmd.history_main(["check", str(tmp_path / "good.json"), "--label", "main", "--history", hist]) == 0
    assert tools_cmd.history_main(["check", str(tmp_path / "bad.json"), "--label", "main", "--history", hist, "--markdown"]) == 2
    assert "regressed" in capsys.readouterr().out
    assert tools_cmd.history_main(["diff", str(tmp_path / "bad.json"), str(tmp_path / "good.json")]) == 0
    assert tools_cmd.history_main(["show", "--history", hist]) == 0
    assert tools_cmd.history_main(["check", str(tmp_path / "missing.json"), "--history", hist]) == 3
    assert History(hist).latest("main")["verdict"] == good["verdict"]


# ---- pre-registration ------------------------------------------------------------------------------------------------


def test_a_registration_before_the_first_run_protects_and_a_changed_or_late_one_does_not(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = SMA.format(n=20)
    path = _strategy(tmp_path, "s.py", src)
    reg = Registry().register("A 20-bar trend rule earns more than buy-and-hold", source=src, n_trials=1)
    rid = f"reg-{reg['seq']}-{reg['hash'][:8]}"
    ok = verify_strategy(DF, strategy=path, ledger=True, registration=rid)
    row = next(c for c in ok["checks"] if c["id"] == "preregistration")
    assert row["status"] == "info" and row["details"]["same_code"] and row["details"]["before_first_verification"]
    assert "before the first verification" in row["summary"]
    other = _strategy(tmp_path, "t.py", SMA.format(n=30))
    changed = next(c for c in verify_strategy(DF, strategy=other, ledger=True, registration=rid)["checks"] if c["id"] == "preregistration")
    assert not changed["details"]["same_code"] and "does NOT protect" in changed["summary"]
    late = Registry().register("The same rule works", source=src)  # registered after the first run of this code
    again = next(c for c in verify_strategy(DF, strategy=path, ledger=True, registration=f"reg-{late['seq']}-{late['hash'][:8]}")["checks"] if c["id"] == "preregistration")
    assert not again["details"]["before_first_verification"]
    missing = next(c for c in verify_strategy(DF, strategy=path, registration="reg-9-deadbeef")["checks"] if c["id"] == "preregistration")
    assert "not found" in missing["summary"]
    with pytest.raises(ValueError, match="hypothesis"):
        Registry().register("  ")


def test_a_registration_never_moves_the_verdict_and_the_cli_registers(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    path = _strategy(tmp_path, "s.py", SMA.format(n=20))
    assert tools_cmd.register_main(["--hypothesis", "trend works", "--strategy", path, "--n-trials", "3"]) == 0
    assert "registered as reg-1-" in capsys.readouterr().out
    plain = verify_strategy(DF, strategy=path)
    registered = verify_strategy(DF, strategy=path, registration="reg-1-00000000")
    assert plain["verdict"] == registered["verdict"]
    assert tools_cmd.register_main(["--hypothesis", " "]) == 3


# ---- hold-out oracle -------------------------------------------------------------------------------------------------


def test_the_oracle_answers_with_the_training_number_while_both_agree_and_spends_budget_on_disagreement(tmp_path: Path) -> None:
    tolerant = HoldoutOracle(tmp_path / "o1.jsonl")
    tolerant.init(DF, holdout=0.3, budget=2, threshold=1000.0, sigma=0.1)  # nothing can disagree by 1000 Sharpe points
    flat = _strategy(tmp_path, "flat.py", "import numpy as np\n\n\ndef signal(df):\n    return np.ones(len(df), dtype=int)\n")
    a = tolerant.query(DF, flat)
    assert a["consistent"] and a["budget_left"] == 2 and "training" in a["kind"]
    assert tolerant.query(DF, flat)["repeated"]  # the same variant is answered from the log, not asked again
    strict = HoldoutOracle(tmp_path / "o2.jsonl")
    strict.init(DF, holdout=0.3, budget=3, threshold=1e-9, sigma=0.1)  # any difference is a disagreement
    b = strict.query(DF, flat)
    assert not b["consistent"] and b["budget_left"] == 2 and "hold-out" in b["kind"]
    assert strict.status() == {"queries": 1, "budget": 3, "budget_left": 2, "holdout": 0.3, "data": strict.status()["data"]}


def test_the_oracle_refuses_other_data_a_second_init_a_spent_budget_and_a_changed_file(tmp_path: Path) -> None:
    oracle = HoldoutOracle(tmp_path / "o.jsonl")
    with pytest.raises(ValueError, match="not initialised"):
        oracle.status()
    oracle.init(DF, budget=1, threshold=1e-9, sigma=0.0)
    with pytest.raises(ValueError, match="already exists"):
        oracle.init(DF)
    with pytest.raises(ValueError, match="not the data"):
        oracle.query(synthetic_ohlcv(1500, seed=5), _strategy(tmp_path, "a.py", SMA.format(n=20)))
    a = _strategy(tmp_path, "a.py", SMA.format(n=20))
    first = oracle.query(DF, a)  # threshold ~0: any difference is a disagreement and spends the only unit
    assert not first["consistent"] and first["budget_left"] == 0
    with pytest.raises(ValueError, match="used up"):
        oracle.query(DF, _strategy(tmp_path, "b.py", SMA.format(n=25)))
    oracle.log.path.write_text(oracle.log.path.read_text().replace('"budget": 1', '"budget": 99'))
    with pytest.raises(ValueError, match="changed"):
        oracle.status()
    for bad in ({"holdout": 0.9}, {"budget": 0}):
        with pytest.raises(ValueError):
            HoldoutOracle(tmp_path / "z.jsonl").init(DF, **bad)


def test_the_oracle_is_deterministic_and_has_a_cli(tmp_path: Path, capsys) -> None:
    csv = tmp_path / "d.csv"
    DF.to_csv(csv, index=False)
    strat = _strategy(tmp_path, "a.py", SMA.format(n=20))
    outs = []
    for name in ("o1.jsonl", "o2.jsonl"):
        f = str(tmp_path / name)
        assert tools_cmd.oracle_main(["init", "--ohlcv", str(csv), "--file", f]) == 0
        assert tools_cmd.oracle_main(["query", "--ohlcv", str(csv), "--strategy", strat, "--file", f]) == 0
        outs.append(capsys.readouterr().out)
    assert outs[0].split("oracle ready")[-1].split("\n", 1)[1] == outs[1].split("oracle ready")[-1].split("\n", 1)[1]
    assert tools_cmd.oracle_main(["status", "--file", str(tmp_path / "nope.jsonl")]) == 3


# ---- portfolio -------------------------------------------------------------------------------------------------------


def test_effective_number_counts_independent_series() -> None:
    assert effective_number(np.eye(5)) == pytest.approx(5.0)
    assert effective_number(np.ones((5, 5))) == pytest.approx(1.0)


def test_a_portfolio_of_clones_counts_one_and_a_diverse_one_counts_more(tmp_path: Path) -> None:
    clones = [_strategy(tmp_path, f"c{i}.py", SMA.format(n=20 + i % 2)) for i in range(4)]
    diverse = [
        _strategy(tmp_path, "d1.py", SMA.format(n=20)),
        _strategy(tmp_path, "d2.py", "import numpy as np\n\n\ndef signal(df):\n    return np.where(np.arange(len(df)) % 3 == 0, 1, 0)\n"),
        _strategy(tmp_path, "d3.py", "import numpy as np\n\n\ndef signal(df):\n    return np.where(np.arange(len(df)) % 7 < 3, -1, 1)\n"),
    ]
    a = verify_portfolio(DF, clones, names=[f"c{i}" for i in range(4)])
    b = verify_portfolio(DF, diverse)
    assert a["effective_number"] < b["effective_number"] and a["clusters"] < b["clusters"]
    assert set(a) >= {"best", "reality_check", "ensemble", "luck_risk", "summary", "correlation"}
    assert b["best"]["trials_used"] == max(1, round(b["effective_number"]))
    with pytest.raises(ValueError, match="at least two"):
        verify_portfolio(DF, clones[:1])
    with pytest.raises(ValueError, match="names"):
        verify_portfolio(DF, clones, names=["x"])


def test_the_portfolio_cli_and_mcp_tool(tmp_path: Path, capsys) -> None:
    csv = tmp_path / "d.csv"
    DF.to_csv(csv, index=False)
    paths = [_strategy(tmp_path, f"s{i}.py", SMA.format(n=15 + 10 * i)) for i in range(3)]
    assert tools_cmd.portfolio_main(["--ohlcv", str(csv), *paths]) == 0
    assert json.loads(capsys.readouterr().out)["effective_number"] > 0
    assert mcp.verify_portfolio(str(csv), paths)["clusters"] >= 1
    assert tools_cmd.portfolio_main(["--ohlcv", str(csv), paths[0]]) == 3


# ---- doctor ----------------------------------------------------------------------------------------------------------


def _codes(result: dict) -> set[str]:
    return {f["code"] for f in result["findings"]}


def test_the_doctor_recognises_providers_and_names_their_traps() -> None:
    idx = pd.date_range("2024-01-02", periods=60, freq="D")
    base = {"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100.0}
    yahoo = pd.DataFrame({"Date": idx.strftime("%Y-%m-%d"), **{k.title(): v for k, v in base.items()}, "Adj Close": 10.2})
    r = diagnose(yahoo)
    assert r["provider"] == "yahoo" and {"adjusted_prices", "timezone", "bar_label"} <= _codes(r)
    binance = pd.DataFrame({
        "open_time": (idx.astype("int64") // 10**3).to_numpy(), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0,
        "close_time": 0, "quote_volume": 1.0, "number_of_trades": 5, "taker_buy_base_volume": 1.0, "taker_buy_quote_volume": 1.0,
    })
    r = diagnose(binance)
    assert r["provider"] == "binance" and "epoch_unit" in _codes(r)
    mt5 = pd.DataFrame({"<DATE>": idx.strftime("%Y.%m.%d"), "<TIME>": "10:00:00", "<OPEN>": 1.0, "<HIGH>": 2.0, "<LOW>": 0.5, "<CLOSE>": 1.5, "<TICKVOL>": 0, "<VOL>": 0, "<SPREAD>": 2})
    r = diagnose(mt5)
    assert r["provider"] == "mt5" and {"timezone", "zero_volume", "tick_volume"} <= _codes(r)
    tv = pd.DataFrame({"time": idx.strftime("%Y-%m-%dT%H:%M:%SZ"), **{k: v for k, v in base.items()}, "RSI": 50.0})
    r = diagnose(tv)
    assert r["provider"] == "tradingview" and "indicator_columns" in _codes(r)
    databento = pd.DataFrame({
        "ts_event": (idx.astype("int64")).to_numpy(), "rtype": 33, "publisher_id": 1, "instrument_id": 7,
        "open": 4_500_000_000_000, "high": 4_510_000_000_000, "low": 4_490_000_000_000, "close": 4_505_000_000_000, "volume": 10,
    })
    r = diagnose(databento)
    assert r["provider"] == "databento" and r["status"] == "error" and "fixed_point_prices" in _codes(r)


def test_the_doctor_finds_generic_table_problems_and_reads_files(tmp_path: Path) -> None:
    idx = pd.date_range("2024-01-01", periods=50, freq="h")
    df = pd.DataFrame({"timestamp": idx, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0})
    shuffled = pd.concat([df.iloc[25:], df.iloc[:25], df.iloc[:2]])
    r = diagnose(shuffled)
    assert {"unsorted", "duplicate_times"} <= _codes(r) and r["status"] == "error"
    clean = diagnose(df)
    assert clean["status"] == "ok" and clean["provider"] is None
    path = tmp_path / "x.csv"
    df.assign(timestamp=df["timestamp"].astype(str)).to_csv(path, index=False)
    assert diagnose(path)["rows"] == 50
    assert "no_time_column" in _codes(diagnose(df.drop(columns="timestamp")))
    with pytest.raises(ValueError, match="provider must be"):
        diagnose(df, "nasdaq")
    gappy = df.drop(index=range(10, 20)).reset_index(drop=True)
    assert "gaps" in _codes(diagnose(gappy))


def test_the_doctor_cli_exit_codes(tmp_path: Path, capsys) -> None:
    idx = pd.date_range("2024-01-01", periods=30, freq="h")
    good = tmp_path / "g.csv"
    pd.DataFrame({"timestamp": idx.astype(str), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0}).to_csv(good, index=False)
    assert tools_cmd.doctor_main([str(good)]) == 0
    bad = tmp_path / "b.csv"
    pd.DataFrame({"timestamp": list(idx.astype(str))[::-1], "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0}).to_csv(bad, index=False)
    assert tools_cmd.doctor_main([str(bad)]) == 2
    assert "unsorted" in capsys.readouterr().out
    assert tools_cmd.doctor_main([str(tmp_path / "nope.csv")]) == 3


def test_the_new_commands_are_dispatched_and_the_tools_are_listed(tmp_path: Path, monkeypatch) -> None:
    import sys

    from monte_neo.cli import entry

    for name in ("history", "register", "oracle", "portfolio", "doctor"):
        monkeypatch.setattr(sys, "argv", ["monte-neo", name, "--help"])
        with pytest.raises(SystemExit) as exc:
            entry.main()
        assert exc.value.code == 0
    for tool in (mcp.register_hypothesis, mcp.compare_certificates, mcp.holdout_query, mcp.verify_portfolio, mcp.diagnose_data):
        assert tool in mcp.TOOLS


def test_mcp_registration_and_comparison_tools(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = _strategy(tmp_path, "s.py", SMA.format(n=20))
    reg = mcp.register_hypothesis("a trend rule works", strategy_path=path, n_trials=2)
    assert reg["id"].startswith("reg-1-")
    csv = tmp_path / "d.csv"
    DF.to_csv(csv, index=False)
    a = verify_strategy(DF, strategy=path)
    b = verify_strategy(DF, strategy=_strategy(tmp_path, "l.py", LEAK))
    (tmp_path / "a.json").write_text(json.dumps(a))
    (tmp_path / "b.json").write_text(json.dumps(b))
    assert mcp.compare_certificates(str(tmp_path / "a.json"), str(tmp_path / "b.json"))["regression"]
    assert mcp.diagnose_data(str(csv))["rows"] == len(DF)
