"""Phantom mean reversion: ``verify --legs``, ``verify --null-test`` and the ``--returns`` summary regression."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.cli.verify_cmd import main
from monte_neo.verify.legs import load_legs, rederive, verify_legs, write_fixed_returns
from monte_neo.verify.nulltest import null_test
from monte_neo.verify.phantom import pair_pnl, random_walk_pair, rolling_ols

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "phantom_pairs"
BARS, WINDOW = 3000, 100


def _legs_table(booking: str, seed: int = 11) -> pd.DataFrame:
    log_y, log_x = random_walk_pair(BARS, 0.01, np.random.default_rng(seed))
    res = pair_pnl(log_y, log_x, WINDOW)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=BARS, freq="h"), "px_y": np.exp(log_y), "px_x": np.exp(log_x),
        "qty_y": res["qty_y"], "qty_x": res["qty_x"], "reported_return": res["booked"] if booking == "buggy" else res["tradable"],
    }).iloc[WINDOW + 1:].reset_index(drop=True)


def test_phantom_term_is_the_hedge_refit() -> None:
    """booked - tradable == -q * (d_beta * x_t + d_alpha): the closed form of the paper."""
    log_y, log_x = random_walk_pair(1500, 0.01, np.random.default_rng(3))
    res = pair_pnl(log_y, log_x, 60)
    a, b, _ = rolling_ols(log_y[None], log_x[None], 60)
    a, b = a[0], b[0]
    q = res["qty_y"]
    d_b, d_a = np.zeros_like(b), np.zeros_like(a)
    d_b[1:], d_a[1:] = np.diff(b), np.diff(a)
    expected = -q * (d_b * log_x + d_a)
    got = res["phantom"]
    assert np.allclose(got[62:], expected[62:], atol=1e-12)


def test_wrong_booking_is_rejected_and_right_booking_passes() -> None:
    bad = verify_legs(_legs_table("buggy"), periods_per_year=8760)
    good = verify_legs(_legs_table("fixed"), periods_per_year=8760)
    row = next(c for c in bad["checks"] if c["id"] == "accounting_mismatch")
    assert bad["verdict"] == "REJECT" and row["status"] == "fail"
    assert bad["metrics"]["reported_sharpe"] > 5 > abs(bad["metrics"]["derived_sharpe"])
    assert good["verdict"] != "REJECT"
    assert next(c for c in good["checks"] if c["id"] == "accounting_mismatch")["status"] == "pass"
    assert any("shift(1)" in a for a in bad["next_actions"])


def test_fixed_returns_are_what_the_legs_earn(tmp_path: Path) -> None:
    table = _legs_table("buggy")
    out = write_fixed_returns(load_legs(table), tmp_path / "fixed.csv")
    fixed = pd.read_csv(out)
    truth = _legs_table("fixed")["reported_return"].to_numpy()[1:]
    assert np.allclose(fixed["return"].to_numpy(), truth, atol=1e-8)


def test_quantities_shifted_by_one_row_are_named() -> None:
    table = _legs_table("fixed")
    table[["qty_y", "qty_x"]] = table[["qty_y", "qty_x"]].shift(-1).fillna(0.0)
    report = verify_legs(table, periods_per_year=8760)
    mismatch = next(c for c in report["checks"] if c["id"] == "accounting_mismatch")
    assert mismatch["status"] == "fail" and "shifted by one bar" in mismatch["summary"]


def test_costs_column_is_subtracted() -> None:
    table = _legs_table("fixed")
    table["cost"] = 0.0001
    table["reported_return"] = table["reported_return"] - 0.0001
    report = verify_legs(table, periods_per_year=8760)
    assert next(c for c in report["checks"] if c["id"] == "accounting_mismatch")["status"] == "pass"
    assert rederive(load_legs(table)).shape[0] == len(table) - 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.drop(columns=["qty_x"]), "both px_ and qty_"),
        (lambda d: d.drop(columns=["reported_return"]), "reported_return"),
        (lambda d: d.assign(px_x=-1.0), "positive"),
        (lambda d: d.iloc[:10], "at least 30"),
        (lambda d: d.drop(columns=["date"]), "date column"),
    ],
)
def test_bad_legs_input_is_an_error_not_a_verdict(mutate, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_legs(mutate(_legs_table("fixed")))


def test_null_test_separates_the_two_bookings() -> None:
    def booked(prices: pd.DataFrame) -> np.ndarray:
        return pair_pnl(np.log(prices["leg1"].to_numpy()), np.log(prices["leg2"].to_numpy()), WINDOW)["booked"]

    def tradable(prices: pd.DataFrame) -> np.ndarray:
        return pair_pnl(np.log(prices["leg1"].to_numpy()), np.log(prices["leg2"].to_numpy()), WINDOW)["tradable"]

    bad = null_test(booked, n_paths=30, bars=1500)
    good = null_test(tradable, n_paths=30, bars=1500)
    assert bad["verdict"] == "REJECT" and bad["checks"][1]["id"] == "edge_on_noise" and bad["checks"][1]["status"] == "fail"
    assert good["verdict"] == "PASS"


def test_null_test_rejects_a_strategy_that_returns_nothing_usable() -> None:
    with pytest.raises(ValueError, match="one return per bar"):
        null_test(lambda p: np.zeros((3, 3)), n_paths=20, bars=200)


def test_cli_exit_codes_on_the_example_files(tmp_path: Path) -> None:
    for mode, expected in (("buggy", 2), ("fixed", 0)):
        legs = tmp_path / f"legs_{mode}.csv"
        _legs_table(mode).to_csv(legs, index=False)
        assert main(["--legs", str(legs), "--periods-per-year", "8760", "--out", str(tmp_path / f"{mode}.json")]) == expected
        assert main(["--null-test", f"{EXAMPLES / f'pairs_{mode}.py'}:pnl", "--null-paths", "30", "--null-bars", "1500"]) == expected
    assert main(["--legs", str(tmp_path / "missing.csv")]) == 3
    assert main(["--null-test", str(tmp_path / "missing.py")]) == 3


def test_cli_legs_fixed_out_feeds_returns_without_a_traceback(tmp_path: Path) -> None:
    legs, fixed = tmp_path / "legs.csv", tmp_path / "fixed.csv"
    _legs_table("buggy").to_csv(legs, index=False)
    assert main(["--legs", str(legs), "--legs-fixed-out", str(fixed)]) == 2
    assert fixed.is_file()
    assert main(["--returns", str(fixed)]) in (0, 1, 2)  # regression: this used to end in KeyError: 'total_return'


def test_demo_phantom_runs() -> None:
    assert main(["--demo-phantom"]) == 0
