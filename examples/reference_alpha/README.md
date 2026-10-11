# Reference alpha 1: diversified trend following (`trend_v1`)

> **Notice.** Not investment advice. Monte-Neo is a research and verification tool. Its reports, examples and reference strategies illustrate a method; they are not a recommendation, an offer or a call to buy, sell or trade any instrument, and not a promise of profit. Simulated and past results do not predict future returns. Trading can lose money, including more than the initial capital when leverage is used. Decisions and their consequences are yours; consult a licensed adviser if you need advice.

## What it is

A deliberately simple, low-return, robust strategy, documented honestly. It is diversified time-series trend following
with volatility targeting, the textbook managed-futures idea (Moskowitz, Ooi and Pedersen, "Time Series Momentum", 2012;
Hurst, Ooi and Pedersen, "A Century of Evidence on Trend-Following Investing", 2017). Its purpose is to show what a
modest, rule-based strategy looks like when an independent verifier tests it: modest numbers, long flat periods, and
verdicts that depend on the market, not on the code. All parameters were fixed in advance and never optimised.

Files: `trend_v1.py` (the `signal(df)` function), `make_data.py` (synthetic universes), this README. The CSV files
are generated, not committed.

## Rules

| Part | Rule |
|------|------|
| Universe | A long table: `timestamp, symbol, open, high, low, close[, volume]`; the more uncorrelated symbols, the better |
| Signal per symbol | Mean of `sign(close_t / close_(t-L) - 1)` for L = 63, 126, 252 bars, from closes up to bar t only; value in {-1, -1/3, 1/3, 1} |
| Size per symbol | `signal * (10% / sqrt(n_symbols)) / sigma`; `sigma` = EWMA volatility (span 60) of daily returns, annualised with 252 |
| Per-symbol cap | `abs(weight) <= 2 / n_symbols` |
| Rebalance | Monthly, in 4 weekly tranches: 4 sleeves rebalance every 21 bars at offsets 0, 5, 10, 15; the weight is their average |
| No-trade band | A sleeve keeps its old weight while the new target is within 10% of the target (same side) |
| Warm-up | Flat until the 252-bar lookback and the volatility estimate exist (about one year) |
| Fills | A weight from the close of bar t is traded at the open of bar t+1 (causal) |
| Gross cap | The engine scales every timestamp with gross > 1 down proportionally. The per-symbol cap allows gross up to 2, so when all symbols trend the same way the engine halves the book: realised risk is below the 10% target then, and there is no leverage |

Long and short positions are used; the verifier switches to `long_short` automatically when the signal has shorts.

## What to expect

From the literature, not a promise: on long, diversified histories (many markets, decades) trend following has shown
a net Sharpe ratio of roughly 0.3 to 0.7, drawdowns of 15 to 30 percent, and multi-year flat or losing periods.
It tends to pay most in sustained moves and to lose in whipsaws. Expect a similar or worse picture on a short history,
fewer markets, or after costs. Treat any year as noise.

## When it works and why

| Situation | Why trend following earns |
|-----------|---------------------------|
| Long, persistent moves in many markets at once | Several lookbacks agree, positions stay on the right side while the move lasts |
| Diversification across asset classes | Trends in different markets are weakly correlated, so the portfolio Sharpe is higher than a single market's |
| Slow reaction of prices to news (under-reaction, flows) | The behavioural and flow explanations in the papers above |
| Large crises that develop over months | Short positions or flat positions avoid part of a long decline |
| Low costs and monthly turnover | The edge is small; tranches and the no-trade band keep costs below it |

## When it does not work and why

| Situation | Why it fails |
|-----------|--------------|
| Ranges and whipsaws | Signals flip after each reversal; every trade buys late and sells late |
| Sharp V-reversals (spring 2009, April 2020) | Positions built in the fall are on the wrong side of the rebound |
| Regimes where all markets move together | Diversification disappears; the book is one big bet and the volatility target understates risk |
| A single instrument | Little diversification, so a handful of trades decide the result |
| High costs or high frequency | The gross edge is small; costs and spread eat it |
| Crowding and post-publication decay | The idea is public and widely traded; the historical premium may be lower now |
| Very short history | Fewer than a few trend cycles: the result is mostly luck (see the seed table below) |

## How to fix and "retrain" without overfitting

Rules:

1. Never re-tune the windows (63, 126, 252), the target volatility or the bands on recent performance.
2. Only the volatility estimate updates automatically (it is part of the rules).
3. Review the universe once a year, causally: add or drop markets using only information known at that date, and
   keep delisted names in the history.
4. Any rule change is a new version (`trend_v2.py`): register it with `monte-neo register` before testing it, and let
   the ledger count it (`--ledger`), so the Deflated Sharpe sees every variant you tried.

| Symptom | Diagnosis (Monte-Neo check) | Action |
|---------|-----------------------------|--------|
| Losses in a quiet, choppy year | `period_consistency`, `walk_forward_stability`: one bad period among profitable ones | Do nothing; this is the expected cost of trend following |
| Net return negative, gross positive | `cost_margin`, `net_profitability`: break-even cost near or below the modelled cost | Cut turnover (wider band), trade cheaper markets, or stop |
| Sharpe good in-sample, weak on holdout | `holdout_consistency`, `deflated_sharpe`: selection effects | Count every variant in `--n-trials` or the ledger; do not pick the best |
| Few markets, results jump around | `sharpe_confidence`, `track_record`: wide interval, short history | Add uncorrelated markets or get more history; do not trust the number |
| Verdict flips with the data sample | `walk_forward_stability`, `timing_significance` | Treat as "no proven edge"; keep size small |
| Live results far from the test | `delay_sensitivity`, `spread_estimate`, `capacity`: costs or delays understated | Re-run with measured costs (`--costs-file`) and the real execution delay |
| Drawdown beyond the stated range | `walk_forward_stability` and the drawdown in the certificate | Reduce the target volatility (a new, registered version), do not chase the signal |

## How to verify it yourself

```bash
cd examples/reference_alpha
python make_data.py                      # writes trends.csv, random.csv, choppy.csv here (not committed)
monte-neo register --hypothesis "trend_v1: diversified trend following earns after costs on trending data, not on random walks" \
    --strategy trend_v1.py --n-trials 1   # before the first run
monte-neo verify --ohlcv trends.csv --strategy trend_v1.py --n-trials 1
monte-neo verify --ohlcv random.csv --strategy trend_v1.py --n-trials 1
monte-neo verify --ohlcv choppy.csv --strategy trend_v1.py --n-trials 1
```

Each run takes about 3 seconds.

## Measured verdicts (default seeds, 12 symbols, 12 years of business days, default costs)

Measured with the commands above, `--n-trials 1`; the three look-ahead checks (truncation, perturbation, static lint)
pass on all three sets.

| Data | Verdict | Net return | Max drawdown | Sharpe (ann.) | Deflated Sharpe | Notes |
|------|---------|-----------:|-------------:|--------------:|----------------:|-------|
| `trends.csv` | PASS_WITH_WARNINGS | +18.38% | 21.80% | 0.30 | 0.844 | Buy and hold of the same symbols: +62.21% (planted drift is positive on average). Timing beats 94% of shifted copies (p 0.070), warning. |
| `random.csv` | PASS_WITH_WARNINGS | +11.74% | 18.24% | 0.22 | 0.768 | Luck on one path: no data edge exists. Deflated Sharpe is below 0.95 and timing beats only 84% of shifted copies. |
| `choppy.csv` | REJECT | -32.89% | 36.16% | -0.65 | 0.015 | `net_profitability` fails. |

Both PASS_WITH_WARNINGS rows carry a survivorship warning (synthetic symbols all live to the last bar).

The single-path numbers are noisy, which is the point. The same generators with 8 other seeds (1000 to 1007),
net total return after costs:

| Data | Net return per seed | Mean |
|------|---------------------|-----:|
| trends | +42.1, +2.5, +1.3, +27.4, +43.9, +20.0, +39.8, +31.1 % | +26.0% |
| random | +12.2, -0.4, -25.1, -0.2, -1.6, +0.3, -10.2, +5.7 % | -2.4% |
| choppy | +2.8, -2.6, -23.6, -2.7, -6.1, -3.0, -9.8, +3.6 % | -5.2% |

Read it this way: on planted trends the strategy earned on every path, but a modest amount with a wide spread; on random
walks the average is slightly negative (costs) and single paths range from -25% to +12%, so a lucky
path can look like an edge. Do not judge it by one run. In the unit test the assertion on random walks is therefore the
Deflated Sharpe below 0.95, not the sign of the return.
