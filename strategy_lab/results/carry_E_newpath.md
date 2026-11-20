# Carry E_btc_eth_slow: re-check through the new Monte-Neo carry path (`verify --carry`, branch x/honest-research)

Not investment advice. Holdout (>= 2025-01-01) not read: every table is cut at 2024-12-31 before the verifier sees it. Nothing trades.

## Inputs
- One table per coin (BTCUSDT, ETHUSDT): `timestamp, spot_close, perp_close, funding_rate` (daily summed funding a long pays), 2020-01-01..2024-12-31 (1827 bars; discovery + validation) and validation only 2021-01-01..2024-12-31 (1461 bars). Files and certificates: `strategy_lab/work/carry/newpath/` (not committed).
- Rule: `signal_E.py`, the E signal of `carry_track.py` (30-day mean funding, enter > 0.0002/day, exit <= 0.00005, decisions weekly on calendar phase 0, hysteresis), 1 = hold the hedged pair. It reproduces the simulator's held days exactly (0 mismatched days of 1827 for both coins).
- Costs: all-in per fill from `binance_costs.py`: BTC spot 12 / perp 7 bps, ETH spot 13 / perp 8 bps (VIP0 fee + spread); entry and exit pay both legs. n_trials = 2165 = 104 (strategy-file grids, `lab_trials()`) + 2016 (screening ledger now) + 45 (carry plateau points), same rule as the earlier 790 (ledger has grown since).
- Limits of the path: one pair per run (E holds two coins, so each coin is verified alone at 100% of capital; no portfolio run exists), a flat cost with no margin account and no 5% capital cost, no weekly-phase scan. Margin 50% and the capital cost live only in the simulator.

## Result (arl-rules/1)
| Run | Verdict | ARL / depth | Return (costs x1 / x2) | Trades | Fails |
|---|---|---|---|---|---|
| BTC 2020-24 | REJECT | 1 / 2 of 4 | +79.6% / +75.7% | 6 | implausible_accuracy (hit rate 0.807, z 23), sample_size |
| ETH 2020-24 | REJECT | 1 / 2 of 4 | +107.0% / +103.0% | 5 | implausible_accuracy (0.818), sample_size |
| BTC 2021-24 | REJECT | 1 / 2 of 4 | +43.3% / +40.7% | 5 | same |
| ETH 2021-24 | REJECT | 1 / 2 of 4 | +45.8% / +42.9% | 5 | same |

- Passed in all four: determinism, look-ahead truncation and perturbation probes, repaint, static lint, net profitability, cost margin, 1-bar delay, timing significance, deflated Sharpe 1.000 over 2165 trials, period consistency (5 of 5 years profitable on 2020-24), `carry_decomposition` (profit is funding: BTC +65.5% funding / -0.4% basis, ETH +81.9% / -1.2%).
- Confirmed: ARL 1 (clean data, no leak found by the probes). Level 2 is **unmet**, not "not assessed", and so levels 3-9 are not reached. Why: (a) `implausible_accuracy`: the hedged pair is up about 81% of held days because funding is persistent and positive; this is a property of carry, not a leak (the truncation probe is clean), but the path has no exemption, so the check blocks level 2; (b) `sample_size`: 5-6 closed trades in five years (weekly decisions with a 30-day filter), minimum 30. Neither can be fixed without changing the strategy or the checker, which was not done.
- Warnings that are artifacts of this path: `alpha_after_beta` uses the always-held hedged pair as the benchmark (beta 0.8-0.97 to it, alpha ~0, t between -2.2 and 0.7), not BTC. The Lab's own BTC beta is -0.00 (HAC t of the mean return 3.73). `regime_stability`: only 1% of bars fall (the instrument is hedged).

## Reconciliation of P&L
Simulator `carry_track.simulate` with zero costs and zero capital cost, validation 2021-24, against the path's convention (spot return - perp return + funding, weights = spot notional share of equity, same held days): sum of daily returns 0.3524 vs 0.3511 (difference -0.4%, below 5%), cumulative +42.22% vs +42.03%, max daily difference 0.017 pp. The remaining gap is funding on mean vs previous-day notional and the price ratio between legs. Reported by the path itself with costs, without capital cost: BTC +43.3% and ETH +45.8% on 2021-24 at 100% capital each; the simulator's net 4.9% a year (+21.6% over 4 years) is after the 5% capital cost on about 77% deployed and the 50% margin, so the figures are not comparable except through the zero-cost check above.

## Known contamination of validation (not corrected)
1. The simulator was rewritten after validation was first read (margin accounting error, first result Sharpe 5.4 / +156% in 2021).
2. Margin 50% was chosen after 25% gave liquidations (E Sharpe 1.1 at 25%). The new path has no margin model, so it does not test this assumption.
3. Mean yearly funding of all coins was printed once before pre-registration (see `carry_track.md`). Validation is therefore exploratory evidence, not blind.

## Gates for the holdout
| Gate | Result | Status |
|---|---|---|
| ARL >= 6 and depth >= 2 | ARL 1, depth 2 (REJECT on BTC and ETH) | **fails** |
| DSR >= 0.95 at the worst phase | path DSR 1.000 (n_trials 2165); worst-of-7 phases 1.00, Sharpe 4.92 from `carry_track` (not rerun in the path); unsmoothed Sharpe about 2.9 | passes (with the serial-correlation caveat) |
| Profit at costs x2 | positive in all four runs; simulator Sharpe 4.52 | passes |
| Beta ~ 0 with t >= 2 | BTC beta -0.00, HAC t 3.73 (Lab); path benchmark is the pair itself, not BTC | passes on the Lab figure |
| Capacity >= 250k USDT | about 21.5M (1% ADV rule, Lab; the new path does not compute it) | passes |

**Admission to the holdout: no.** The ARL gate fails and is blocked by two checks that are structural for a slow carry rule. The holdout stays sealed.

---

# After block 9 (Monte-Neo `86e0a3c`: basis accuracy, accrual sample, future-funding probe, margin, baskets)

Same rules: tables cut at 2024-12-31, no holdout, no code changed. Not investment advice.

## Setup
- Basket run: one table `symbol, timestamp, spot_close, perp_close, funding_rate, volume` (BTC+ETH, volume = dollar volume of the thinner leg), `signal_E_basket.py` = the E rule per coin with weight 1/3 of equity per held coin (E deploys 50% of equity per coin including 50% margin, so the notional share is 1/3). Python `verify_carry(..., capital_cost_apr=0.075, perp_leverage=2, rebalance_every=7, n_trials=2165)`: 0.075 = 5% on the deployed capital (notional + 50% margin); leverage 2 = margin 50%. Basket costs 13/8 bps (the ETH, higher, pair for both coins). Per-coin runs: weight 1, own costs (BTC 12/7, ETH 13/8), same apr and leverage. Each at 2020-24 and at 2021-24. Scripts and certificates (`cert9_*.json`): `strategy_lab/work/carry/newpath/` (not committed).
- n_trials recomputed: 104 + 2016 + 45 = **2165** (ledger unchanged since the first run).

## Result (arl-rules/1)
| Run | Verdict | ARL / depth | Net return (x1 / x2) | Sharpe | maxDD | Effective accrual periods | Phases (worst of 7) | alpha vs spot, t |
|---|---|---|---|---|---|---|---|---|
| Basket BTC+ETH 2020-24 | REJECT | 4 / 2 | +31.7% / +29.6% | 4.94 | 2.4% | 161 (11 trades) | +30.9% | +5.9% a year, 5.4 |
| Basket 2021-24 | REJECT | 4 / 1 | +11.0% / +9.4% | 4.14 | 2.3% | 125 (10 trades) | +10.5% | +2.8%, 3.8 |
| BTC 2020-24 | REJECT | 4 / 2 | +35.5% / +32.5% | 4.15 | 3.7% | 163 (6) | +33.6% | +6.5%, 4.7 |
| ETH 2020-24 | REJECT | 4 / 2 | +60.7% / +57.3% | 4.94 | 3.4% | 170 (5) | +59.9% | +10.1%, 5.9 |
| BTC 2021-24 | REJECT | 4 / 1 | +14.3% / +12.1% | 3.51 | 3.7% | 139 (5) | +13.2% | +3.5%, 3.5 |
| ETH 2021-24 | REJECT | 4 / 1 | +19.3% / +16.8% | 4.06 | 3.4% | 134 (5) | +18.7% | +4.6%, 4.0 |

Per-coin 100%-capital numbers are not comparable with the basket (different weight). A table that starts on 2021-01-01 has no funding history for the 30-day filter, so the rule is flat in January 2021 (funding was highest then): the 2021-24 totals are lower than the simulator's validation for that reason, not because of a rule change.

## What is confirmed, failed, not assessed
- **Confirmed (ARL 1-3 reached, all runs):** determinism, look-ahead truncation and perturbation, repaint, `carry_future_probe` (6 probes, signal unchanged), `implausible_accuracy` now passes (basis hit rate 0.51, z 0.9), net profitability, break-even cost 173-200 bps against 21 modeled, 1-bar delay, timing significance, sample size passes on 125-170 effective accrual periods (min 30), DSR 1.000 over 2165 trials, carry decomposition (funding +76.8% vs basis -1.0%), beta to the spot reference -0.00, all 7 rebalance phases profitable.
- **Capped at ARL 4:** (a) basket: `survivorship` (BTC and ETH are today's survivors, no delisted list); single coins skip that row but still end at 4; (b) `alpha`-path items for level 4 depth: **L4 D1 unmet** (needs `monte-neo alpha` with scores, not available for a carry rule), **L4 D2 unmet on 2021-24** (met on 2020-24), L4 D4 not assessed (sealed holdout never opened).
- **Not assessed:** levels 5-9 ("it is new alpha": `hidden_short_volatility` and `residual_alpha` not run; L5 D3 unmet). `data_independence` was skipped in the basket runs ("needs strategy code").
- **Failed check:** `carry_margin` (verdict REJECT because of it): perpetual rose 2453% (ETH) / 630% (BTC) above entry while held in 2020-21, 97-267% in 2021-24; buffer at 2x is 50%. This check has no top-ups, whereas the simulator tops margin up from spot sales to 50% and had 0 liquidations. Not overridden: the fail stands for a rule that holds through a bull run with no margin management in the checker, and it matches the known dependence of E on the margin assumption (25% margin: 6 liquidations, Sharpe 1.1 in the simulator).
- Warnings: `regime_stability` (loses in falling markets, -2.3% over 31% of bars; 108-131% of profit from rising markets), `few_decisions` on single coins (5-6 entries in 5 years), `survivorship` on the basket.

## Reconciliation with the simulator
Basket 2020-24: path net +31.67% against simulator net +32.39% (same period, costs x1, capital cost 5%, margin 50%): difference 2.2%, below 5%. Costs x2: +29.6% against +30.2%. Zero-cost, zero-capital-cost check from the first section still holds (-0.4%). Held days are identical (0 mismatches). Capacity: the path reports 1.6B USDT at 1% of the bar volume (8.1B at 5%); the Lab's ADV rule gives about 21.5M. The two differ by about 75 times (the path measures the fill against the bar volume of the thinner leg, the Lab against the 10th percentile of the position-to-volume ratio); the difference was not resolved, both are far above 250k.

## Gates for the holdout (after block 9)
| Gate | Result | Status |
|---|---|---|
| ARL >= 6 and depth >= 2 | ARL 4, depth 2 (2020-24) / 1 (2021-24); REJECT on `carry_margin` | **fails** |
| DSR >= 0.95 at the worst phase | DSR 1.000 (2165 trials); worst of 7 phases +30.9% / +10.5%, positive in all | passes (Sharpe 4.1-4.9; effective sample 125-161) |
| Profit at costs x2 | +29.6% (2020-24), +9.4% (2021-24) | passes |
| Beta about 0, t >= 2 | beta -0.00 to the spot reference, alpha t 5.4 / 3.8 (reference is equal-weight BTC+ETH spot, not BTC alone; Lab: beta to BTC -0.00, HAC t 3.73) | passes |
| Capacity >= 250k USDT | 1.6B (path, 1% of bar volume), 21.5M (Lab) | passes |

**Admission to the holdout: no.** One gate fails (ARL 4 < 6, with `carry_margin` rejecting and survivorship capping the basket). The other four pass. Validation is contaminated as listed above (simulator rewritten after the first read, margin 50% chosen after 25% liquidated, yearly funding printed before pre-registration), so even the passing gates are exploratory evidence. The holdout stays sealed.

---

# After block 10 (Monte-Neo `1450cc9`: declared collateral policy, bar highs, attribution, ex-ante universe, capacity formula, basket independence)

Pre-registered first: `strategy_lab/batches/carry_prereg_addendum.json` (committed before this run). Tables cut at 2024-12-31, holdout not read, no code changed. Not investment advice.

## Setup (as registered)
- **E**: basket BTC+ETH, weight 1/3 per held coin, costs 13/8 bps, leverage 2, maintenance 4% (the simulator's value), capital cost 0.075, phases 7, reference BTC. **Collateral policy:** top up to 50% when the buffer falls below 25% of notional, transfer arrives 1 bar later, 13 bps on the amount moved. Inputs add the bar high of the perpetual (Lab day-high with the bad-tick cap) and quote volumes (daily volume x close, USDT) per leg.
- **E_pit** (new attempt, n_trials 2166; E stays 2165): the same signal on a pool of the 12 Lab coins, held only while the coin is in the top 2 by perp quote volume over the previous 30 bars on each weekly date (recomputed by the verifier). Costs 15/10 bps for all pool coins.

## Results
| Run | Verdict | ARL / depth | Net return (x1 / x2) | Sharpe | Worst phase | Residual alpha t | Hidden short vol | Margin |
|---|---|---|---|---|---|---|---|---|
| E 2020-24 | REJECT | 4 / 2 | +31.7% / +29.6% | 4.94 | +30.9% | 5.4 (hurdle 3.0) | none (skew 0.4) | **fail**: 1 of 11 episodes liquidated despite the policy (about 3 Jan 2021) |
| E 2021-24 | PASS_WITH_WARNINGS | 4 / 1 | +11.0% / +9.4% | 4.14 | +10.5% | 3.8 | none (skew 2.2; funding paid when negative 2.5% of earned) | warn: survives only with 17 transfers totalling 811% of the perp notional (cost 1.05%) |
| E_pit 2020-24 | REJECT | 4 / 2 | +31.3% / +28.9% | 4.85 | +30.5% | 5.5 | none | fail, same episode |
| E_pit 2021-24 | PASS_WITH_WARNINGS | 4 / 1 | +10.7% / +8.8% | 3.96 | +10.2% | 3.8 | none | warn, same |

- **Margin:** with no collateral management 6 of 11 (full) and 6 of 10 (2021-24) episodes liquidate at 2x. With the declared policy 2021-24 survives but only with a large cash reserve (811% of the perpetual notional moved in 17 transfers: the spot leg has to be sold or cash held, which the capital cost 5% on 1.5x notional only partly prices); on 2020-24 one episode is liquidated in the first days of January 2021 even with the policy, so the policy as registered does not hold in the 2020-21 bull run. The simulator (top-up at 30%, no delay) had 0 liquidations; the difference is the 25% trigger with a one-bar delay and the intrabar high. Not tuned.
- **Attribution (level 5):** residual alpha against BTC and the equal-weight spot passes (t 5.4 on 2020-24, 3.8 on 2021-24); hidden short volatility passes (no short-volatility payoff, skew positive, negative funding takes 2.5% of what funding earned, worst basis bar -0.31%).
- **Survivorship:** E keeps the cap (hand-made list). E_pit: the ex-ante rule is recomputed and all positions are inside it (`universe_rule` pass, 2834 / 2148 positions), but no coin of the pool stops trading inside the sample (the Lab has no delisted perps), so **the cap stays at ARL 4**. The rule changed almost nothing (top 2 by volume were BTC and ETH nearly always: +31.3% against +31.7%); E_pit adds nothing but the attempt count.
- **Capacity (new formula, min of the two legs' quote volume x share over one bar, divided by the weight change):** E 2020-24: 10.9M USDT at 1%, 54.6M at 5%, 109M at 10% (BTC 55M, ETH 66M at 5%); 2021-24: 13.3M / 66.5M / 133M. The earlier 1.6B was inflated by the hedged index (about 100) and is retracted. The Lab's ADV rule gave 21.5M: same order.
- **Levels:** 1-3 confirmed in all runs; `data_independence` now passes for the basket; `implausible_accuracy` (0.51) and sample size (161 / 125 effective periods) pass. L4: D1 unmet (no `alpha` scores path), D2 unmet on 2021-24, D4 not assessed (sealed holdout never opened). L5: D3 unmet (more history) and on 2021-24 D1 unmet; D4 not assessed. L6-9 not reached; the cap is survivorship.
- Reconciliation with the simulator unchanged: path +31.67% against simulator +32.39% on 2020-24 (2.2%).

## Gates for the holdout (E / E_pit)
| Gate | E | E_pit | Status |
|---|---|---|---|
| ARL >= 6 and depth >= 2 | ARL 4, depth 2 (full) / 1 (2021-24); REJECT on 2020-24 (margin) | same | **fails both** |
| DSR >= 0.95 at the worst phase | DSR ~1.000 (2165 trials), worst of 7 phases +30.9% / +10.5% | DSR ~1.000 (2166), +30.5% / +10.2% | passes both |
| Profit at costs x2 | +29.6% / +9.4% | +28.9% / +8.8% | passes both |
| Beta about 0, t >= 2 | beta -0.00; residual alpha t 5.4 / 3.8 | beta 0.00; t 5.5 / 3.8 | passes both |
| Capacity >= 250k USDT | 10.9M at 1% of bar volume (new formula) | same | passes both |

**Admission to the holdout: no, for E and for E_pit.** The ARL gate fails (4 against 6, survivorship cap and the margin failure on 2020-24). The margin result also says the economics need a cash reserve of many times the perp notional under this policy; validation remains contaminated (simulator rewritten after the first read, margin 50% chosen after 25% liquidated, yearly funding printed before pre-registration). The holdout stays sealed.
