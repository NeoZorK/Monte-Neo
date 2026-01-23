# Quick Start

Get up and running with Monte-Neo in 3 steps.

## 1. Launch the CLI

```bash
uv run monte-neo
```

## 2. Download Data

Navigate to `📊 Download Market Data`, enter `BTCUSDT`, timeframe `1h`, and select `365 days`.

## 3. Generate

Select `🎯 Set Target Metrics` and define your goals (e.g., Profit Factor > 2).
Then select `🚀 Generate Indicator` and let the engine find the best solution for you.

### Dynamic Mode (Evolutionary Algorithms)

To use the power of genetic algorithms:
1. In the configuration menu, ensure `dynamic` is selected in indicator types.
2. The engine will first perform a random search for candidates.
3. If enough candidates are found, it will automatically start **Evolutionary Optimization**, cross-breeding and mutating the best strategies to find even more robust indicators.
4. All results are automatically validated with **Monte Carlo simulations**.

---

**Tip**: Use arrow keys to navigate the menus and Space to select checkboxes.
For more details on how genetic algorithms work in Monte-Neo, see the [Dynamic Indicators Guide](../project/dynamic_indicators.md).
