"""Claimed numbers against verified ones (``--claim``)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
from trap_data import planted_momentum_ohlcv  # noqa: E402

from monte_neo.cli.verify_cmd import main as cli_main  # noqa: E402
from monte_neo.mcp import tools  # noqa: E402
from monte_neo.verify import model_from_costs, recheck_certificate, verify_grid, verify_strategy  # noqa: E402
from monte_neo.verify.checks import NEXT_ACTIONS  # noqa: E402
from monte_neo.verify.claim import claim_row, parse_claim  # noqa: E402

TRAPS = Path(__file__).parents[1] / "traps" / "strategies"
VERIFIED = {"sharpe": 1.2, "total_return": 0.40, "max_drawdown": 0.15, "n_trades": 300.0, "win_rate": 0.55, "profit_factor": 1.6}


def test_parse_claim_accepts_aliases_percent_strings_and_files(tmp_path: Path) -> None:
    got = parse_claim({"Sharpe_Ratio": "2.1", "return": "85%", "drawdown": -0.12, "trades": "1,200", "hit_rate": 62, "profit_factor": 1.9})
    assert got == {"sharpe": 2.1, "total_return": 0.85, "max_drawdown": 0.12, "n_trades": 1200.0, "win_rate": 0.62, "profit_factor": 1.9}
    assert parse_claim({"max_drawdown": "12%"})["max_drawdown"] == 0.12 and parse_claim({"max_dd": 12})["max_drawdown"] == 0.12
    assert parse_claim({"total_return": 1.85})["total_return"] == 1.85  # returns above 100% are real
    path = tmp_path / "claim.json"
    path.write_text('{"sharpe": 1.5}', encoding="utf-8")
    assert parse_claim(path) == parse_claim(str(path)) == parse_claim('{"sharpe": 1.5}') == {"sharpe": 1.5}


@pytest.mark.parametrize(
    ("claim", "message"),
    [
        ({}, "non-empty JSON object"),
        ({"sharp": 1}, "unknown claim key 'sharp'"),
        ({"sharpe": "high"}, "must be a number"),
        ({"sharpe": True}, "must be a number"),
        ({"sharpe": [1]}, "must be a number"),
        ({"sharpe": float("nan")}, "must be finite"),
        ({"sharpe": 1, "sharpe_ratio": 2}, "given twice"),
        ("[1, 2]", "non-empty JSON object"),
        ('{"sharpe": 1, "sharpe": 2}', "duplicate key"),
    ],
)
def test_parse_claim_errors(claim: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_claim(claim)  # type: ignore[arg-type]


def test_matching_conservative_and_inflated_claims() -> None:
    honest = claim_row(parse_claim({"sharpe": 1.25, "total_return": 0.41, "max_drawdown": 0.15, "n_trades": 305, "win_rate": 0.56, "profit_factor": 1.65}), VERIFIED)
    assert honest["status"] == "pass" and "claim matches" in honest["summary"]
    modest = claim_row(parse_claim({"sharpe": 0.5, "total_return": 0.1, "max_drawdown": 0.4}), VERIFIED)
    assert modest["status"] == "pass" and modest["details"]["metrics"]["sharpe"]["status"] == "conservative"
    for key, value in (("sharpe", 2.0), ("total_return", 0.9), ("max_drawdown", 0.05), ("n_trades", 500), ("win_rate", 0.7), ("profit_factor", 2.5)):
        row = claim_row(parse_claim({key: value}), VERIFIED)
        assert row["status"] == "fail" and row["details"]["metrics"][key]["status"] == "overclaimed", key
        assert "claim overstated" in row["summary"] and row["category"] == "claim"


def test_tolerances_are_generous_enough_for_rounding() -> None:
    edge = {"sharpe": 1.49, "total_return": 0.435, "max_drawdown": 0.14, "n_trades": 314, "win_rate": 0.579, "profit_factor": 1.85}
    assert claim_row(edge, VERIFIED)["status"] == "pass"
    just_over = {"sharpe": 1.2 + 0.31}
    assert claim_row(just_over, VERIFIED)["status"] == "fail"


def test_unverifiable_metrics_are_reported_not_failed() -> None:
    weights = {**VERIFIED, "win_rate": None, "profit_factor": None}
    row = claim_row({"win_rate": 0.9, "profit_factor": 3.0}, weights)
    assert row["status"] == "skip" and "nothing in the claim can be verified" in row["summary"]
    mixed = claim_row({"win_rate": 0.9, "sharpe": 1.2}, weights)
    assert mixed["status"] == "pass" and mixed["details"]["metrics"]["win_rate"]["status"] == "not verifiable"
    assert claim_row({"sharpe": 9.0}, {**VERIFIED, "sharpe": float("nan")})["status"] == "skip"


@pytest.fixture(scope="module")
def data():
    df = planted_momentum_ohlcv()
    return df, model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(df))


def test_end_to_end_verdicts_and_certificate_ids(data) -> None:
    df, model = data
    plain = verify_strategy(df, strategy=TRAPS / "momentum.py", model=model)
    m, stats = plain["metrics"], plain["charts"]["trade_stats"]
    truth = {"sharpe": round(m["sharpe_annualized"], 2), "total_return": round(m["total_return"], 3), "max_drawdown": round(m["max_drawdown"], 3),
             "n_trades": m["n_closed_trades"], "win_rate": stats["win_rate"], "profit_factor": stats["profit_factor"]}
    honest = verify_strategy(df, strategy=TRAPS / "momentum.py", model=model, claim=truth)
    row = next(c for c in honest["checks"] if c["id"] == "claim_consistency")
    assert row["status"] == "pass" and honest["verdict"] == plain["verdict"]
    assert "claim_consistency" not in {c["id"] for c in plain["checks"]} and "claim" not in plain["reproducibility"]["settings"]
    lie = verify_strategy(df, strategy=TRAPS / "momentum.py", model=model, claim={**truth, "sharpe": 9.0, "total_return": "400%"})
    assert lie["verdict"] == "NEEDS_MORE_EVIDENCE" and any("claim_consistency" in r for r in lie["reasons"])
    assert lie["certificate_id"] != honest["certificate_id"] != plain["certificate_id"]
    assert lie["reproducibility"]["settings"]["claim"]["sharpe"] == 9.0
    assert NEXT_ACTIONS["claim_consistency"] in lie["next_actions"]


def test_a_claim_that_a_leaky_strategy_makes_is_checked_too() -> None:
    from monte_neo.backtest import synthetic_ohlcv

    report = verify_strategy(synthetic_ohlcv(1500, seed=13), strategy=TRAPS / "lookahead_shift.py", claim={"total_return": 5.0, "sharpe": 8})
    assert report["verdict"] == "REJECT" and next(c for c in report["checks"] if c["id"] == "claim_consistency")["status"] == "fail"


def test_weights_and_grids_take_a_claim(data) -> None:
    df, model = data
    weights = verify_strategy(df, signals=0.5 * (df["close"].pct_change().fillna(0) > 0).astype(float).to_numpy(), model=model, claim={"win_rate": 0.9, "sharpe": 50})
    row = next(c for c in weights["checks"] if c["id"] == "claim_consistency")
    assert row["details"]["metrics"]["win_rate"]["status"] == "not verifiable" and row["details"]["metrics"]["sharpe"]["status"] == "overclaimed"
    grid = verify_grid(df, {"lookback": [1, 2, 3]}, strategy=TRAPS / "momentum_params.py", model=model, claim={"sharpe": 99})
    assert next(c for c in grid["checks"] if c["id"] == "claim_consistency")["status"] == "fail"


def test_recheck_reproduces_a_claimed_certificate(data, tmp_path: Path) -> None:
    df, model = data
    cert = json.loads(json.dumps(verify_strategy(df, strategy=TRAPS / "momentum.py", model=model, claim={"sharpe": 9.0})))
    path = tmp_path / "cert.json"
    path.write_text(json.dumps(cert), encoding="utf-8")
    again = recheck_certificate(path, df, strategy=TRAPS / "momentum.py")
    assert again["reproduced"] is True and again["engine_version"]


def test_cli_and_mcp_accept_a_claim(data, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    df, _ = data
    csv = tmp_path / "prices.csv"
    df.to_csv(csv, index=False)
    claim = tmp_path / "claim.json"
    claim.write_text(json.dumps({"sharpe": 12.0, "total_return": 5.0}), encoding="utf-8")
    out = tmp_path / "cert.json"
    code = cli_main(["--ohlcv", str(csv), "--strategy", str(TRAPS / "momentum.py"), "--claim", str(claim), "--commission-bps", "1", "--slippage-bps", "1", "--out", str(out)])
    assert code == 1  # NEEDS_MORE_EVIDENCE
    assert "claim_consistency" in {c["id"] for c in json.loads(out.read_text())["checks"]}
    assert cli_main(["--ohlcv", str(csv), "--strategy", str(TRAPS / "momentum.py"), "--claim", '{"bogus": 1}']) == 3
    assert "unknown claim key" in capsys.readouterr().out
    result = tools.verify_strategy(str(csv), strategy_path=str(TRAPS / "momentum.py"), claim={"sharpe": 12.0}, compact=False)
    assert next(c for c in result["checks"] if c["id"] == "claim_consistency")["status"] == "fail"
    grid = tools.verify_grid(str(csv), str(TRAPS / "momentum_params.py"), {"lookback": [1, 2, 3]}, claim={"sharpe": 99}, compact=False)
    assert grid["verdict"] != "PASS"
    assert "claim" in tools.SERVER_INSTRUCTIONS


def test_report_shows_the_claim_card(data) -> None:
    from monte_neo.verify.report_html import render_html

    df, model = data
    page = render_html(verify_strategy(df, strategy=TRAPS / "momentum.py", model=model, claim={"sharpe": 9.0}))
    assert 'class="cat bad"' in page and "claim" in page and "claim overstated" in page
