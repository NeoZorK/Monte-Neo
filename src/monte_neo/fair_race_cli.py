"""CLI: monte-neo-fair-race — public entrypoint for ClaimBound reproduce."""

from __future__ import annotations

import argparse
import json

from monte_neo.fair_race import run_type_b_scenarios, run_type_c_sweep, return_path_bootstrap, synthetic_ohlcv
import numpy as np


def main() -> None:
    p = argparse.ArgumentParser(description="Monte-Neo fair-race helpers (ClaimBound)")
    p.add_argument("--type", choices=["B", "C", "A_demo"], required=True)
    p.add_argument("--bars", type=int, default=50_000)
    p.add_argument("--combos", type=int, default=256)
    p.add_argument("--scenarios", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    if args.type == "C":
        out = run_type_c_sweep(n_bars=args.bars, combos=args.combos, seed=args.seed)
    elif args.type == "B":
        out = run_type_b_scenarios(n_bars=args.bars, n_scenarios=args.scenarios, seed=args.seed)
    else:
        data = synthetic_ohlcv(args.bars, seed=args.seed)
        rets = np.diff(np.log(data["close"].to_numpy()))
        out = return_path_bootstrap(rets, n_simulations=args.scenarios, seed=args.seed)
        out["type"] = "A_return_path_demo"
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
