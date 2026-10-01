"""Run the quote checks on real recordings and say plainly what happens.

The prices and the exchange timestamps of a recording are real; the latency is not trusted (a VPN or a busy network distorts the
receive time), so every run *assumes* a latency model. Four kinds of strategy run on every recording and scenario:

* honest slow strategies (no leak): they must never be rejected or accused; most have no edge on real prices, and then the
  latency checks are ``skip`` (there is no profit to lose) - the script counts that instead of hiding it;
* a foresight control (``shift(-1)``): it must be rejected by the look-ahead probes;
* a latency-arbitrage pair (one recording traded on the move of another), when two recordings are given.

Run: uv run python scripts/validate_on_real_quotes.py data/real_quotes/*.csv
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.verify.quotes import feed_alias
from monte_neo.verify.quotes_verdict import verify_quotes
from monte_neo.verify.verdict import model_from_costs

SCENARIOS = ("lognormal:5,15", "lognormal:20,60", "constant:50")
MODEL = model_from_costs(commission_bps=0.2, slippage_bps=0.3)


def trend3(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].diff(3).fillna(0.0).to_numpy())


def mean_reversion(df: pd.DataFrame) -> np.ndarray:
    return -np.sign((df["close"] - df["close"].rolling(30).mean()).fillna(0.0).to_numpy())


def breakout(df: pd.DataFrame) -> np.ndarray:
    hi, lo = df["close"].rolling(20).max().shift(1), df["close"].rolling(20).min().shift(1)
    return np.where(df["close"] > hi, 1, np.where(df["close"] < lo, -1, 0)).astype(float)


def fast_momentum(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].diff().fillna(0.0).to_numpy())


def foresight(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].shift(-1) - df["close"]).fillna(0.0).to_numpy()


HONEST = {"trend (3 bars)": (trend3, 1000.0), "mean reversion (30 bars)": (mean_reversion, 1000.0),
          "breakout (20 bars)": (breakout, 5000.0), "fast momentum": (fast_momentum, 100.0)}


def run(table: pd.DataFrame, symbol: str, fn, bar_ms: float, scenario: str, **extra) -> dict:
    started = time.time()
    try:
        return _run(table, symbol, fn, bar_ms, scenario, started, **extra)
    except ValueError as exc:  # a recording too short for this bar length is skipped and counted, not hidden
        return {"verdict": "SKIPPED", "exchange_return": 0.0, "arrival_return": 0.0, "status": {}, "reason": str(exc), "seconds": 0.0}


def _run(table: pd.DataFrame, symbol: str, fn, bar_ms: float, scenario: str, started: float, **extra) -> dict:
    report = verify_quotes(table, signal_fn=fn, symbol=symbol, bar_ms=bar_ms, model=MODEL, samples=40, latency_model=scenario, **extra)
    status = {c["id"]: c["status"] for c in report["checks"]}
    return {
        "verdict": report["verdict"], "exchange_return": report["metrics"]["return_exchange_clock"],
        "arrival_return": report["metrics"]["return_arrival_clock"], "status": status, "seconds": round(time.time() - started, 1),
    }


def planted_pair(one: pd.DataFrame, lead_ms: float = 2000.0) -> pd.DataFrame:
    """The real quotes of one symbol as the leader, plus a follower that repeats the leader's mid ``lead_ms`` later.

    The price path (volatility, jumps, clustering) is real; only the follower's lag is planted, so the edge is known to exist.
    """
    stamps = pd.to_datetime(one["timestamp"], utc=True).to_numpy(dtype="datetime64[ns]").astype(np.int64)
    mid = (0.5 * (one["bid"] + one["ask"])).to_numpy()
    behind = np.searchsorted(stamps, stamps - int(lead_ms * 1e6), side="right") - 1
    lag_mid = mid[np.clip(behind, 0, None)]
    lead = one.assign(symbol="REAL_LEADER", latency_ms=0.0)[["timestamp", "bid", "ask", "latency_ms", "symbol"]]
    lag = pd.DataFrame({"timestamp": one["timestamp"].to_numpy(), "bid": lag_mid * (1 - 1e-5), "ask": lag_mid * (1 + 1e-5), "latency_ms": 0.0, "symbol": "PLANTED_FOLLOWER"})
    return pd.concat([lead, lag], ignore_index=True)


def main(paths: list[str]) -> int:
    frames = []
    for path in paths:
        frame = pd.read_csv(path)
        frames.append(frame)
    quotes = pd.concat(frames, ignore_index=True)
    symbols = sorted(quotes["symbol"].unique())
    rows: list[dict] = []
    for symbol in symbols:
        one = quotes[quotes["symbol"] == symbol]
        print(f"\n== {symbol}: {len(one):,} real quotes, {one['timestamp'].iloc[0]} .. {one['timestamp'].iloc[-1]}")
        for name, (fn, bar_ms) in HONEST.items():
            for scenario in SCENARIOS:
                r = {"symbol": symbol, "strategy": name, "scenario": scenario, "kind": "honest", **run(one, symbol, fn, bar_ms, scenario)}
                rows.append(r)
                print(f"  honest  {name:24s} {scenario:16s} {r['verdict']:20s} plain {r['exchange_return']:+.4f}  arrival {r['arrival_return']:+.4f}")
        r = {"symbol": symbol, "strategy": "foresight shift(-1)", "scenario": SCENARIOS[1], "kind": "leaky", **run(one, symbol, foresight, 1000.0, SCENARIOS[1])}
        rows.append(r)
        print(f"  LEAKY   {'foresight shift(-1)':24s} {SCENARIOS[1]:16s} {r['verdict']:20s} lookahead_truncation: {r['status'].get('lookahead_truncation')}")
    if len(symbols) >= 2:
        lead, follow = symbols[0], symbols[1]  # a real pair, nothing planted
        alias = feed_alias(lead)

        def lead_lag(df: pd.DataFrame) -> np.ndarray:
            return np.sign(df[f"{alias}_close"].diff(3).fillna(0.0).to_numpy())

        for scenario in SCENARIOS:
            r = {"symbol": f"{follow} on {lead}", "strategy": "real lead-lag (100 ms bars)", "scenario": scenario, "kind": "pair",
                 **run(quotes, follow, lead_lag, 100.0, scenario, feeds=[lead], probes=False)}
            rows.append(r)
            print(f"  pair    {follow} on {lead} {scenario:16s} {r['verdict']:20s} plain {r['exchange_return']:+.4f}  arrival {r['arrival_return']:+.4f}")
    def vol(sym: str) -> float:  # the most volatile recording gives the planted edge room to beat the costs
        sub = quotes[quotes["symbol"] == sym]
        mid = (0.5 * (sub["bid"] + sub["ask"])).to_numpy()
        return float(np.std(np.diff(np.log(mid[:: max(1, len(mid) // 900)]))))

    base = max(symbols, key=vol)
    pair = planted_pair(quotes[quotes["symbol"] == base])

    def planted(df: pd.DataFrame) -> np.ndarray:
        return np.sign(df["REAL_LEADER_close"].diff(10).fillna(0.0).to_numpy())

    print(f"\n== planted lead-lag on the real path of {base} (the follower repeats it 2 s later)")
    for scenario in ("lognormal:20,60", "constant:500", "constant:1500", "constant:2500"):
        r = {"symbol": "PLANTED_FOLLOWER on REAL_LEADER", "strategy": "planted lead-lag (200 ms bars)", "scenario": scenario, "kind": "planted",
             **run(pair, "PLANTED_FOLLOWER", planted, 200.0, scenario, feeds=["REAL_LEADER"], probes=False)}
        rows.append(r)
        print(f"  planted {scenario:16s} {r['verdict']:20s} plain {r['exchange_return']:+.4f}  arrival {r['arrival_return']:+.4f}  arrival_lookahead {r['status'].get('arrival_lookahead')}")
    honest = [r for r in rows if r["kind"] == "honest" and r["verdict"] != "SKIPPED"]
    profitable = [r for r in honest if r["exchange_return"] > 0]
    accused = [r for r in honest if r["verdict"] == "REJECT" and r["status"].get("net_profitability") != "fail"]
    flagged = [r for r in profitable if "warn" in (r["status"].get(k) for k in ("arrival_lookahead", "latency_tolerance", "latency_monte_carlo"))]
    leaky = [r for r in rows if r["kind"] == "leaky"]
    print("\nSUMMARY")
    skipped = [r for r in rows if r["verdict"] == "SKIPPED"]
    print(f"  recordings: {len(symbols)}; honest runs: {len(honest)} ({len(skipped)} skipped: recording too short for the bar length)")
    print(f"  honest runs profitable on the plain backtest: {len(profitable)}")
    print(f"  honest runs rejected for a reason other than losing money (false accusations): {len(accused)}")
    print(f"  profitable honest runs with a latency warning: {len(flagged)} of {len(profitable)}")
    print(f"  foresight controls rejected by the probes: {sum(1 for r in leaky if r['verdict'] == 'REJECT')} of {len(leaky)}")
    out = Path(paths[0]).parent / "validation_results.json"
    out.write_text(json.dumps(rows, indent=2, default=str))
    print(f"  details: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
