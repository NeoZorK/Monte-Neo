"""Minimal research export — fee-aware SMA sweep on synthetic OHLCV."""

from monte_neo.backtest import ExecutionModel, export_sma_sweep, synthetic_ohlcv


def main() -> None:
    ohlc = synthetic_ohlcv(100_000, seed=42)
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
    out = export_sma_sweep(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        combos=16,
        model=model,
        device="auto",
    )
    print(
        {
            "device": out.get("device"),
            "fallback_reason": out.get("fallback_reason"),
            "combos": out.get("combos"),
            "best_return": out.get("best_return"),
        }
    )


if __name__ == "__main__":
    main()
