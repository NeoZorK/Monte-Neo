# Lessons from the Strategy Lab (November 2026)

What an honest search with Monte-Neo found, including where it went wrong. Each lesson names what changed in
Monte-Neo because of it. The Strategy Lab is the maintainer's reproducible search pipeline; its strategies are research
examples. **Not investment advice.**

## 1. A strong validation is not a passed holdout

A cross-sectional trend basket of 18 crypto coins (Donchian channel position, 55-day window, weekly) looked strong on
validation 2021-2024: net Sharpe 1.57 (1.54 at doubled costs), Deflated Sharpe 0.74, Monte-Neo verdict
`PASS_WITH_WARNINGS`, ARL 5. A gate was written and committed before the sealed holdout was read (net Sharpe above zero
at doubled costs, drawdown not below -45 %). The holdout 2025-01 to 2026-10, opened once, gave net Sharpe -0.02 (-0.06 at
doubled costs), -8.5 % and a -35 % drawdown. The gate failed and the family was closed.

Why: 2021 alone returned +667 % and carried the validation; the signal's beta to BTC was about 0.5, so the basket was
largely the market in a strong year. **What it confirms:** the sealed holdout and the gate written before it are the
part of the protocol that caught this; no statistic on the validation period did.

## 2. Hidden trials cannot be detected; they must be documented

In the full calibration (350,000 cases), the best of 100 noise strategies reported as a single trial reached ARL 4 in
93 % of cases. The selected curve is indistinguishable from one honest lucky trial. **Changed in Monte-Neo (v0.56):**
ARL levels 4 and above need a record of the trials: the trial ledger (`--ledger`, now also for `monte-neo alpha`),
`--trials-from`, or a pre-registration made before the first verification. Without it the level is capped at 3.

## 3. A check that exists on one path only silently blocks power

No planted single-asset edge passed ARL 4 (0 of 112,000 cases): level 5 needs residual alpha and hidden short
volatility, which only the cross-sectional and carry paths computed. **Changed (v0.56):** `verify` computes both for a
single strategy against the asset it trades. Planted single-asset edges reaching level 6 went from 0 % to 30 %.

## 4. Literature parameters plus a sealed holdout can pass, and the honest result is small

A book of three published premia on 16 ETFs (time-series trend, inverse-volatility risk parity, bond trend and carry),
parameters from the papers, one third each, was pre-registered before any combined run. Validation 2015-2020: net
Sharpe 0.76. The ETF holdout 2021-01 to 2026-11, opened once: net Sharpe 0.74 (0.70 at doubled costs), maximum drawdown
-4.1 %, 2.4 % a year at 3.3 % volatility. The gate passed. Monte-Neo's verdict on the holdout returns was
`NEEDS_MORE_EVIDENCE`: with 17 trials, 5.8 years is not enough for significance (Deflated Sharpe 0.48). **What it shows:**
a robust result can be real and still too small and too uncertain to sell as alpha; reporting it with the verdict is the
honest form.

## 5. Short validation windows cannot certify slow premia

A strategy with a true Sharpe ratio of 0.5 to 0.8 cannot reach a Deflated Sharpe of 0.95 on six years of daily data once
more than a handful of trials are priced. Gates for such strategies should be written as a holdout or forward criterion
(Sharpe at doubled costs, drawdown, worst week), with the Monte-Neo verdict reported next to it, not as a DSR threshold
that only a very strong or overfit result can meet.

## 6. Phantom profit in pairs backtests

Re-estimating a hedge ratio on a rolling window and booking position times the change of the spread creates P&L that no
trader can earn. In a private backtest it turned a reported Sharpe of +2.6 to +3.0 into a tradable -2.0 to -2.9.
See [Phantom profit](phantom-profit.md) and the paper in `paper/phantom-mean-reversion/`.

## 7. Demo (testnet) execution is evidence of process, not of slippage

Exchange testnets have thin order books and are reset from time to time. A forward record should measure P&L at mainnet
prices with the pre-registered cost model, record every testnet fill together with the mainnet price at that moment,
reconcile the two books every day, and anchor the journal in time. **Added (v0.56):** `monte-neo deploy`, see
[Deploy to a demo testnet](deploy.md).
