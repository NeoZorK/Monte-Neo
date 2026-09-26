"""Trap Suite: known ways a backtest lies, each with its expected verdict.

Add a trap = add ``strategies/<name>.py`` with ``signal(df)`` + a row in TRAPS.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from monte_neo.backtest import run_bar_backtest
from monte_neo.verify import model_from_costs, verify_grid, verify_strategy

STRATEGY_DIR = Path(__file__).parent / "strategies"

LOOKAHEAD_IDS = ("lookahead_truncation", "lookahead_perturbation", "lookahead_static_lint", "implausible_accuracy")

# name, dataset, allowed verdicts, required check statuses
TRAPS = [
    ("lookahead_shift", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail", "implausible_accuracy": "fail"}),
    ("centered_window", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("global_zscore", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail"}),
    ("bfill_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("high_turnover", "random_walk", {"REJECT"}, {"net_profitability": "fail"}),
    ("hourly_close_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("reverse_rolling", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("full_polyfit", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail", "lookahead_static_lint": "warn"}),
    ("full_rank", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail", "lookahead_static_lint": "warn"}),
    ("resample_max_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("target_encoding_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("sma_cross", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE"}, {}),
    ("expanding_zscore", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("momentum", "planted", {"PASS", "PASS_WITH_WARNINGS"}, {"net_profitability": "pass", "deflated_sharpe": "pass"}),
]
HONEST = {"high_turnover", "sma_cross", "momentum", "expanding_zscore"}
# Parameterized strategies exercised through verify_grid (not in TRAPS).
GRID_STRATEGIES = {"sma_params", "momentum_params"}


def _statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


def test_every_strategy_file_is_in_manifest() -> None:
    files = {p.stem for p in STRATEGY_DIR.glob("*.py")}
    assert files == {t[0] for t in TRAPS} | GRID_STRATEGIES


@pytest.mark.parametrize(("name", "dataset", "verdicts", "required"), TRAPS, ids=[t[0] for t in TRAPS])
def test_trap_verdict(name: str, dataset: str, verdicts: set[str], required: dict[str, str], request: pytest.FixtureRequest) -> None:
    df = request.getfixturevalue(dataset)
    model = model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(df)) if dataset == "planted" else None
    report = verify_strategy(df, strategy=STRATEGY_DIR / f"{name}.py", model=model)
    statuses = _statuses(report)
    assert report["verdict"] in verdicts, report["reasons"]
    for check_id, status in required.items():
        assert statuses[check_id] == status, (check_id, report["reasons"])
    if name in HONEST:
        # Honest code must never be accused of look-ahead (false positives kill trust).
        assert all(statuses[c] != "fail" for c in LOOKAHEAD_IDS), report["reasons"]


def test_data_snooping_is_priced_by_n_trials(random_walk) -> None:
    """Best of 200 random strategies passes only if the agent hides n_trials."""
    df = random_walk
    model = model_from_costs(commission_bps=0.5, slippage_bps=0.5, n_bars=len(df))
    rng = np.random.default_rng(0)
    best_ret, best_sig = -np.inf, None
    for _ in range(200):
        sig = np.repeat(rng.integers(0, 2, size=len(df) // 20 + 1), 20)[: len(df)]
        ret = run_bar_backtest(df.open.values, df.high.values, df.low.values, df.close.values, sig, model=model)["total_return"]
        if ret > best_ret:
            best_ret, best_sig = ret, sig
    assert best_ret > 0.0
    hidden = verify_strategy(df, signals=best_sig, model=model)
    honest = verify_strategy(df, signals=best_sig, model=model, n_trials=200)
    assert _statuses(hidden)["deflated_sharpe"] != "fail"
    assert _statuses(honest)["deflated_sharpe"] == "fail"
    assert honest["verdict"] in {"NEEDS_MORE_EVIDENCE", "REJECT"}


def test_grid_on_random_walk_fails_walk_forward(random_walk) -> None:
    grid = {"fast": [5, 10, 20, 40], "slow": [50, 80, 120, 200]}
    report = verify_grid(random_walk, grid, strategy=STRATEGY_DIR / "sma_params.py")
    statuses = _statuses(report)
    assert report["reproducibility"]["n_trials"] == 16
    assert statuses["walk_forward_oos"] == "fail"
    assert report["verdict"] == "REJECT"
    assert all(statuses[c] != "fail" for c in LOOKAHEAD_IDS)


def test_grid_on_planted_edge_passes(planted) -> None:
    model = model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(planted))
    report = verify_grid(planted, {"lookback": [1, 2, 3, 5, 8]}, strategy=STRATEGY_DIR / "momentum_params.py", model=model)
    assert report["grid"]["best_params"] == {"lookback": 1}
    assert _statuses(report)["walk_forward_oos"] == "pass"
    assert report["verdict"] in {"PASS", "PASS_WITH_WARNINGS"}
