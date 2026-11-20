# Carry track: delta-neutral funding carry (long spot / short USD-M perp)

Idea: Claude Sonnet 5.5. Process: Rostyslav Shcherbyna. **Not investment advice.** Nothing trades; no keys; holdout (2025-01-01 on) cut in code and not read.
Code: `scripts/strategy_lab/carry_track.py`; pre-registration: `strategy_lab/batches/carry_prereg.json` (committed before validation was read; see the honest account of what changed after).

## Setup

- Data already in the Lab: 12 coins (BTC, ETH, BNB, XRP, ADA, LTC, LINK, DOGE, DOT, AVAX, ATOM, SOL), daily spot/perp klines and daily summed funding. **Funding starts 2020-01 (not 2019-09), so discovery = 2020 only (about one year).** Validation 2021-2024.
- Always long spot / short perp. The reverse leg (short spot / long perp on negative funding) is not modelled: no borrow-rate data. The strategy is flat when the funding forecast is low.
- Signal: mean daily funding of the last L days (close t), enter above `enter`, exit below `exit` (hysteresis), trade at the close, earn from the next day. Thresholds are tied to the cost arithmetic (round trip about 50 bps, 30-day holding gives about 0.0003/day).
- Costs: spot 10 bps and perp 5 bps VIP0 plus per-coin spread, on every entry, exit, margin top-up and liquidation; x2 doubles fee and spread. Funding is the published daily sum, paid on the mean notional. Basis is marked to market (no entry/exit basis assumption beyond the spread). Capital cost 5% p.a. on deployed capital (spot + margin), always charged (conservative in the zero-rate years). Perp margin 50% of notional (max 2x), topped up from spot sales when the margin ratio falls below 30%; liquidation test at the perp day-high (ratio below 4%, 1% fee, loss at the high).
- n_trials for the deflated Sharpe: 790 (strategy-file grids 104, screening ledger 635, this track 45 declared plateau points; the ledger keeps growing with the night queue).
- Selection rule (pre-registered): discard if discovery Sharpe at x2 costs <= 0; among the rest the highest validation Sharpe at x2 costs. Applied: **E_btc_eth_slow** (BTC+ETH, L=30, enter 0.0002/day, exit 0.00005, weekly decisions, 50% cap per coin).

## Variants on validation 2021-2024 (all five, selected one marked E)

| Variant | disc Sharpe (x1 / x2) | val Sharpe | val x2 | val x0 capital cost | max DD | ann. return | total 2021-24 | beta BTC | alpha t (naive) | DSR | worst-phase Sharpe / DSR | liq. | capacity (USDT, 1% ADV) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_fast_daily | 5.97 / 4.54 | 0.92 | 0.83 | 1.17 | -1.4% | 10.8% | 50.1% | 0.002 | 1.82 | 0.000 | 0.92 / 0.000 | 3 | 2.8M |
| B_weekly | 6.29 / 5.31 | 3.02 | 2.56 | 4.90 | -1.6% | 4.2% | 18.2% | -0.001 | 6.15 | 0.941 | 0.56 / 0.021 | 5 | 3.2M |
| C_very_fast | 6.19 / 4.25 | 2.83 | 2.19 | 3.87 | -1.5% | 4.5% | 19.8% | -0.001 | 5.72 | 0.929 | 2.83 / 0.929 | 6 | 3.8M |
| D_top4_weekly | 4.94 / 3.46 | 1.99 | 0.92 | 3.18 | -2.9% | 3.9% | 16.9% | -0.001 | 4.01 | 0.655 | 0.41 / 0.008 | 2 | 2.0M |
| E_btc_eth_slow | 6.93 / 6.49 | 4.95 | 4.52 | 8.68 | -2.5% | 4.9% | 21.6% | -0.000 | 9.95 | 1.000 | 4.92 / 1.000 | 0 | 21.5M |

Returns by calendar year (return on capital, after the 5% capital cost):

| Variant | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| A_fast_daily | +19.6% (Sh 8.6) | +22.5% (Sh 1.0) | +0.4% (Sh 1.1) | +2.1% (Sh 1.4) |
| B_weekly | +14.3% (Sh 5.1) | -0.4% (Sh -3.7) | +0.5% (Sh 1.2) | +3.4% (Sh 5.8) |
| C_very_fast | +16.7% (Sh 5.6) | -0.0% (Sh -1.0) | +0.6% (Sh 1.5) | +2.1% (Sh 1.5) |
| D_top4_weekly | +15.4% (Sh 3.8) | -0.4% (Sh -2.4) | -0.0% (Sh -0.1) | +1.8% (Sh 2.1) |
| E_btc_eth_slow | +19.5% (Sh 10.6) | -1.6% (Sh -8.4) | +0.0% (Sh 0.1) | +3.4% (Sh 6.2) |

Variant parameters: A L=7 enter 0.0003 exit 0.0001 daily, cap 1/6 per coin, 12 coins; B L=14, same thresholds, weekly; C L=3 enter 0.0004 exit 0.00015 daily; D top-4 coins by L=14 funding, weekly, cap 25%; E BTC+ETH L=30 enter 0.0002 exit 0.00005 weekly cap 50%.
Worst phase = the weekly decision offset (0-6) with the lowest validation Sharpe; daily variants have no phase.

## Selected variant E: robustness

Plateau (L and thresholds scaled, 9 points, validation):

| L days, enter /day | Sharpe | Sharpe x2 | ann. return |
|---|---|---|---|
| L=15,enter=0.00013 | 4.86 | 4.16 | 4.9% |
| L=15,enter=0.00020 | 5.02 | 4.36 | 4.9% |
| L=15,enter=0.00030 | 5.43 | 4.95 | 5.2% |
| L=30,enter=0.00013 | 4.68 | 4.3 | 4.7% |
| L=30,enter=0.00020 | 4.95 | 4.52 | 4.9% |
| L=30,enter=0.00030 | 5.11 | 4.71 | 5.0% |
| L=60,enter=0.00013 | 4.56 | 4.39 | 4.5% |
| L=60,enter=0.00020 | 4.48 | 4.25 | 4.4% |
| L=60,enter=0.00030 | 4.68 | 4.49 | 4.5% |

Perp margin sensitivity (validation) - **the result depends on the margin assumption**:

| perp margin | Sharpe | ann. return | liquidations |
|---|---|---|---|
| 0.25 | 1.09 | 3.0% | 6 |
| 0.5 | 4.95 | 4.9% | 0 |
| 1.0 | 3.9 | 3.0% | 0 |

- HAC (Newey-West, 10 lags) t-statistic of the mean daily return: **3.73** (naive 9.91; returns are strongly autocorrelated, lag-1 0.67, so the naive t is overstated). Beta to BTC about 0.00, correlation -0.03, so the alpha t equals the return t.
- Sharpe first half / second half of validation: 6.24 / 3.63. Worst year: 2022 (-1.6%). Worst 30-day return -0.49%. Max drawdown 2.5%.
- Causality check (own): re-running on data truncated at 2023-01-01 reproduces the earlier returns exactly (max difference 0.0).
- Tail events:

| Window | E cum. return | E worst day | max 1-day perp rally of any coin |
|---|---|---|---|
| 2020-03 crash | not in validation (discovery, E not yet trading) | - | 38% |
| 2021-05 crash | +0.36% | -0.11% | 40% |
| 2022-05 LUNA | -0.06% | -0.03% | 32% |
| 2022-11 FTX | +0.00% | +0.00% | 61% |

  The large perp rallies of 32-61% in a day are in coins E does not hold at that moment or are absorbed by the 50% margin; E had no liquidation. FTX (Nov 2022) and LUNA (May 2022) cost nothing because the funding filter had E flat. The survivors-only universe has no LUNA/FTT/UST perps, so a depeg of a held coin is not tested.
- Capacity by the 1%-of-ADV rule: about 21M USDT for E (BTC and ETH only). This is a participation bound, not a claim that the 2-3 bps spread assumption holds at that size; it is far above 250k.

## Monte-Neo verification (arl-rules/1)

- `verify --returns` (returns path, n-strategies = n_trials, BTC benchmark, plus the Lab's integrity check of the input prices): verdict PASS_WITH_WARNINGS, **ARL 1, depth 0/4**. Warnings: lag-1 autocorrelation 0.67 (unsmoothed Sharpe 2.90 against reported 4.95; funding is a persistent cash flow, so this is expected, not a data fault), and 16% of returns on exact 5 bps multiples (idle zero days).
- `verify --legs` (spot, perp and a funding "leg" for each coin, quantities as share of equity, simple returns): verdict PASS, accounting matches within 10% (unexplained 5.5%), ARL 1, depth 0. Re-derived Sharpe (before capital cost) 8.95. The first attempt with the net return as the reported series was REJECTED with 46% unexplained, because the legs hold no cash leg and the 5% capital cost is not a leg; comparing with the return before that cost passes.
- **Confirmed level: ARL 1 (clean input data, accounting reproduced). Levels 2-9 cannot be assessed on these paths by construction**: look-ahead probes, net-profitability against costs, timing/IC tests, residual alpha, capacity and robustness checks need a strategy file or positions on one OHLCV (`verify --strategy`, `alpha`), and a two-instrument carry has neither. The own truncation check above is evidence for causality, but it is not an ARL credit.

## Gates for the holdout

| Gate | E result | Status |
|---|---|---|
| ARL >= 6 and depth >= 2 | ARL 1, depth 0 | **fails** (cap by construction of the available paths) |
| DSR >= 0.95 at the worst phase | 1.00 (Sharpe 4.92 at the worst of 7 phases) | passes, but the DSR assumes independent returns; the unsmoothed Sharpe is 2.9 |
| Profit at costs x2 | Sharpe 4.52, positive in every year except 2022 (-1.6%) | passes |
| Alpha to BTC t >= 2, or beta about 0 and return t >= 2 | beta 0.00, HAC t 3.73 | passes |
| Capacity >= 250k USDT | about 21M (1% ADV rule) | passes |
| Tail events reported | yes, see above | done |

**The holdout is not opened**: the ARL gate fails and a freeze would need it. Economically the result is modest: 4.9% a year on capital after a 5% capital cost (about 10% gross on about 77% deployed), 21.6% over four years, nearly all of it from 2021 (+19%) and 2024 (+3.4%); 2022-2023 earned about zero because funding was low or negative. That is a funding premium that exists in bull phases, not a regime-free edge.

## What changed after validation was first read (honest account)

1. First validation run used a margin model without top-ups (position sizes drifted with price, which let notional and funding income grow without capital): Sharpe 5.4, +156% in 2021 for E. That was an accounting error, not a result. It is recorded in the work folder only (`result_v1_nomargin.json`, not published).
2. Margin model added (top-ups, liquidation test). With a 25% margin the result was poor (79 liquidations for the basket variants; E Sharpe 1.1). A bad perp high (ETH 2020-03-13, +203% in a day) was filtered as a bad tick (high capped at 10% above max(open, close)).
3. Margin set to 50% (2x max leverage) as the sane retail setting. This was chosen after seeing the 25% result, so validation influenced it; the table above shows the sensitivity. Variants, thresholds and the selection rule were not changed.
4. Before pre-registration the yearly mean funding of all coins was printed once (market-level context for validation), and one summary of the funding files included a post-2025 value; nothing from 2025 on was used.
Anything here is therefore exploratory evidence on validation, not a confirmed result, and the sealed holdout remains the only blind data.

## What blocks admission

The ARL gate (1 against the required 6): the verifier has no path that tests look-ahead, timing and robustness for a spot/perp pair carry, so the strongest honest statement is "clean data, accounting reproduced, return significant after costs, no BTC beta". To pass it, Monte-Neo needs a carry-aware path (two-leg positions with funding, a truncation probe on the signal) - a gap to add to `MONTE_NEO_GAPS.md`. Second: the return is a bull-phase funding premium and is sensitive to the margin setting.
