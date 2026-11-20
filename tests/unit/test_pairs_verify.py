"""``verify --legs --pairs-checks``: econometrics on top of the leg accounting, with honest and dishonest pairs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_pairs_math import ar1, legs_table, rw

from monte_neo.cli.verify_cmd import main
from monte_neo.mcp import tools
from monte_neo.verify.legs import load_legs, rederive, verify_legs
from monte_neo.verify.pairs_verify import NEXT_ACTIONS, PairsOptions, _execution_rows, pairs_checks
from monte_neo.verify.phantom import pair_pnl, random_walk_pair
from monte_neo.verify.schema import VERDICT_JSON_SCHEMA

N = 3000


def rows(report: dict) -> dict[str, dict]:
    return {c["id"]: c for c in report["checks"]}


def walks_table(booking: str) -> pd.DataFrame:
    """Two independent random walks traded by the phantom-prone z-score rule, booked wrongly or from the legs."""
    log_y, log_x = random_walk_pair(N, 0.01, np.random.default_rng(31))
    res = pair_pnl(log_y, log_x, 100)
    df = pd.DataFrame(
        {"px_y": np.exp(log_y), "px_x": np.exp(log_x), "qty_y": res["qty_y"], "qty_x": res["qty_x"],
         "reported_return": res["booked"] if booking == "buggy" else res["tradable"]},
        index=pd.date_range("2024-01-01", periods=N, freq="h"),
    )
    return df.iloc[101:]


def honest_table() -> pd.DataFrame:
    return legs_table(N, seed=40)


OPTS = PairsOptions()


def test_honest_cointegrated_pair_is_not_rejected_and_the_link_is_confirmed() -> None:
    report = verify_legs(honest_table(), periods_per_year=8760, pairs=OPTS)
    by = rows(report)
    assert report["verdict"] in ("PASS", "PASS_WITH_WARNINGS")
    assert by["cointegration_eg"]["status"] == "pass" and by["cointegration_eg"]["details"]["pvalue_bucket"] == "<0.01"
    assert by["cointegration_eg"]["details"]["beta"] == pytest.approx(0.8, abs=0.05)
    assert by["spread_half_life"]["status"] == "pass" and by["rolling_cointegration"]["status"] == "pass"
    assert by["hedge_ratio_stability"]["status"] == "pass"
    assert by["structural_break_spread"]["status"] == "pass" and by["structural_break_hedge"]["status"] == "pass"
    assert by["pair_selection"]["status"] == "info" and "cointegration_johansen" not in by
    assert by["accounting_mismatch"]["status"] == "pass"


def test_independent_random_walks_show_no_link_but_honest_accounting_is_not_rejected() -> None:
    report = verify_legs(walks_table("fixed"), periods_per_year=8760, pairs=OPTS)
    by = rows(report)
    assert by["cointegration_eg"]["status"] in ("fail", "warn")
    assert report["verdict"] in ("NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS")  # never REJECT on econometrics alone
    assert by["accounting_mismatch"]["status"] == "pass"
    assert any("no long-run relationship" in a or "not shown to be stationary" in a for a in report["next_actions"])


def test_phantom_booking_is_still_rejected_with_the_econometrics_on() -> None:
    report = verify_legs(walks_table("buggy"), periods_per_year=8760, pairs=OPTS)
    assert report["verdict"] == "REJECT" and rows(report)["accounting_mismatch"]["status"] == "fail"
    assert rows(report)["cointegration_eg"]["status"] in ("fail", "warn")


def test_certificate_without_pairs_is_unchanged() -> None:
    table = honest_table()
    plain, extended = verify_legs(table, periods_per_year=8760), verify_legs(table, periods_per_year=8760, pairs=OPTS)
    assert [c["id"] for c in plain["checks"]] == [
        "legs_scope", "data_integrity", "accounting_mismatch", "derived_significance",
        "legs_timing_significance", "legs_placebo", "legs_lookahead", "legs_signal_ic",
    ]
    assert extended["checks"][:8] == plain["checks"] and len(extended["checks"]) > 8
    assert plain["certificate_id"] != extended["certificate_id"]
    assert "pairs" not in plain["reproducibility"]["settings"]
    assert set(plain) <= set(VERDICT_JSON_SCHEMA["properties"]) | {"generated_at"}


def broken_table() -> pd.DataFrame:
    """Cointegrated for 1500 bars, then the hedge ratio jumps from 0.8 to 1.6: the relationship is destroyed."""
    rng = np.random.default_rng(41)
    x = 4.6 + 0.01 * rw(N, rng)
    spread = ar1(N, 0.85, rng, 0.004)
    beta = np.where(np.arange(N) < 1500, 0.8, 1.6)
    y = beta * x + spread - np.where(np.arange(N) < 1500, 0.0, 0.8 * 4.6)
    df = pd.DataFrame({"px_y": np.exp(y), "px_x": np.exp(x), "qty_y": 0.0, "qty_x": 0.0}, index=pd.date_range("2024-01-01", periods=N, freq="h"))
    df["reported_return"] = 0.0
    return df


def test_a_destroyed_relationship_is_dated() -> None:
    df = broken_table()
    report = verify_legs(df, periods_per_year=8760, pairs=PairsOptions(break_date=str(df.index[1500])))
    by = rows(report)
    hedge = by["structural_break_hedge"]
    assert hedge["status"] == "fail" and hedge["details"]["break_date"]
    when = pd.Timestamp(hedge["details"]["break_date"])
    assert abs((when - df.index[1500]) / pd.Timedelta(hours=1)) < 120
    assert "changed around" in hedge["summary"]
    assert by["chow_known_date"]["status"] == "warn" or by["chow_known_date"]["status"] == "pass"
    assert report["verdict"] == "NEEDS_MORE_EVIDENCE"
    assert by["hedge_ratio_stability"]["status"] == "warn" and by["hedge_ratio_stability"]["details"]["max"] > 1.4  # the link re-forms at another ratio
    assert any("stopped holding" in a for a in report["next_actions"])


def test_chow_row_passes_on_a_stable_spread() -> None:
    df = honest_table()
    row = rows(verify_legs(df, periods_per_year=8760, pairs=PairsOptions(break_date=str(df.index[1500]))))["chow_known_date"]
    assert row["status"] in ("pass", "warn") and row["details"]["date"] == str(df.index[1500])


def test_three_legs_add_the_johansen_test() -> None:
    rng = np.random.default_rng(42)
    f = rw(N, rng) * 0.01
    df = pd.DataFrame(
        {"px_a": np.exp(4.0 + f + ar1(N, 0.8, rng, 0.003)), "px_b": np.exp(3.0 + 0.5 * f + ar1(N, 0.8, rng, 0.003)), "px_c": np.exp(2.0 + 0.01 * rw(N, rng)),
         "qty_a": 0.0, "qty_b": 0.0, "qty_c": 0.0, "reported_return": 0.0},
        index=pd.date_range("2024-01-01", periods=N, freq="h"),
    )
    j = rows(verify_legs(df, periods_per_year=8760, pairs=OPTS))["cointegration_johansen"]
    assert j["status"] == "pass" and j["details"]["rank"] >= 1 and j["details"]["vector"][0] == 1.0
    df["px_c"] = np.exp(2.0 + 0.01 * rw(N, np.random.default_rng(43)))
    df["px_b"] = np.exp(3.0 + 0.01 * rw(N, np.random.default_rng(44)))
    df["px_a"] = np.exp(4.0 + 0.01 * rw(N, np.random.default_rng(45)))
    assert rows(verify_legs(df, periods_per_year=8760, pairs=OPTS))["cointegration_johansen"]["status"] == "fail"


def test_pair_selection_deflates_the_sharpe_by_the_pairs_screened() -> None:
    table = honest_table()
    table["cost"] = 0.8 * rederive(table).mean()  # a modest edge: 80 % of the profit is paid away
    table["reported_return"] = np.concatenate([[0.0], rederive(table)])
    one = rows(verify_legs(table, periods_per_year=8760, pairs=PairsOptions(pairs_tested=1)))["pair_selection"]
    mid = rows(verify_legs(table, periods_per_year=8760, pairs=PairsOptions(pairs_tested=100)))["pair_selection"]
    many = rows(verify_legs(table, periods_per_year=8760, pairs=PairsOptions(pairs_tested=100000, variants_per_pair=5)))["pair_selection"]
    assert one["details"]["n_trials"] == 1 and many["details"]["n_trials"] == 500000
    assert many["details"]["deflated_sharpe"] < mid["details"]["deflated_sharpe"] < one["details"]["deflated_sharpe"]
    assert (one["status"], mid["status"], many["status"]) == ("pass", "fail", "fail")


def test_legging_and_borrow_rows() -> None:
    table = honest_table()
    out = rows(verify_legs(table, periods_per_year=8760, pairs=PairsOptions(legging_delay_ms=5_400_000.0, bar_ms=3_600_000.0, borrow_bps=300.0, borrow_unavailable=0.3)))
    leg, bor = out["legging_risk"], out["borrow_risk"]
    assert leg["status"] in ("pass", "warn") and leg["details"]["scan"][0]["damage"] == 0.0
    assert len(leg["details"]["scan"]) > 5 and leg["details"]["test_delay_bars"] == pytest.approx(1.5, abs=0.01)
    assert bor["status"] in ("pass", "warn") and bor["details"]["blocked_bars"] > 0
    by_bars = rows(verify_legs(table, periods_per_year=8760, pairs=PairsOptions(legging_delay_bars=4.0)))["legging_risk"]
    assert by_bars["details"]["test_delay_bars"] == 4.0 and by_bars["status"] in ("pass", "warn")
    assert "borrow_risk" not in rows(verify_legs(table, periods_per_year=8760, pairs=OPTS))


def test_a_profit_that_lives_in_the_second_leg_turns_into_a_loss_when_it_is_late() -> None:
    n = 300
    r = np.where(np.arange(n) % 2 == 0, 0.01, -0.01)  # the second leg alternates; the first leg is a quiet walk
    df = pd.DataFrame({"px_y": np.exp(0.0001 * np.cumsum(np.ones(n))), "px_x": np.exp(np.cumsum(r)), "qty_y": 0.0, "qty_x": np.sign(r)}, index=pd.date_range("2024-01-01", periods=n, freq="h"))
    df["reported_return"] = np.concatenate([[0.0], rederive(df)])
    row = _execution_rows(df, PairsOptions(legging_delay_bars=1.0), 8760.0, "log")[0]
    assert row["status"] == "warn" and "turns into a loss" in row["summary"] and row["details"]["scan"][3]["total"] < 0.0


def test_execution_rows_skip_when_the_legs_lose_money() -> None:
    table = honest_table().assign(qty_y=lambda d: -d["qty_y"], qty_x=lambda d: -d["qty_x"])
    assert rederive(table).sum() < 0
    out = rows(verify_legs(table, periods_per_year=8760, pairs=PairsOptions(borrow_bps=100.0)))
    assert out["legging_risk"]["status"] == "skip" and out["borrow_risk"]["status"] == "skip"


def test_big_borrow_fee_warns() -> None:
    out = rows(verify_legs(honest_table(), periods_per_year=8760, pairs=PairsOptions(borrow_bps=2_000_000.0)))
    assert out["borrow_risk"]["status"] == "warn"


def test_input_errors() -> None:
    with pytest.raises(ValueError, match="at least 120"):
        pairs_checks(honest_table().iloc[:80])
    one_leg = honest_table().drop(columns=["px_x", "qty_x"])
    with pytest.raises(ValueError, match="two legs"):
        pairs_checks(one_leg)
    assert pairs_checks(honest_table(), None)  # default options


def test_cli_flags_and_exit_codes(tmp_path: Path) -> None:
    legs = tmp_path / "legs.csv"
    honest_table().rename_axis("date").to_csv(legs)
    out = tmp_path / "cert.json"
    args = ["--legs", str(legs), "--periods-per-year", "8760", "--pairs-checks", "--pairs-tested", "20", "--pair-variants", "2",
            "--legging-delay", "1", "--borrow-bps", "100", "--borrow-unavailable", "0.1", "--break-date", "2024-03-01", "--pairs-window", "600", "--out", str(out)]
    assert main(args) in (0, 1)
    cert = json.loads(out.read_text())
    ids = [c["id"] for c in cert["checks"]]
    assert "cointegration_eg" in ids and cert["reproducibility"]["settings"]["pairs"]["pairs_tested"] == 20
    assert main(["--legs", str(legs), "--periods-per-year", "8760"]) == 0


def test_mcp_tool_and_manifest() -> None:
    df = honest_table()
    path = Path(__import__("tempfile").mkdtemp()) / "legs.csv"
    df.rename_axis("date").to_csv(path)
    report = tools.verify_pairs(str(path), pairs_tested=3, legging_delay_bars=1.0, borrow_bps=50.0, periods_per_year=8760.0)
    assert "cointegration_eg" in rows(report) and "borrow_risk" in rows(report)
    assert tools.verify_pairs in tools.TOOLS
    catalogue = tools.verifier_manifest()["checks"]
    assert set(NEXT_ACTIONS) <= set(catalogue)
    assert load_legs(path).shape[0] == len(df)
