# Strategy-type profiles

A trend strategy, a pairs strategy and a short-volatility book fail in different ways. A **profile** tells the verifier
which checks matter for the type, which benchmark to read, and what the tool cannot assess. You choose it; Monte-Neo only
hints.

```bash
monte-neo verify --list-profiles
monte-neo verify --ohlcv data.csv --strategy my_strategy.py --profile trend_cta --out cert.json
```

The certificate gets a `profile` block: the checks the type requires, which of them ran, which did not (with the reason),
and what is not assessed. **A profile never raises a verdict.** A required check that did not run is listed as not run,
never counted as passed.

When you do not pass `--profile`, a run prints a one-line hint if the input looks like a known type (for example funding
and perpetual columns suggest `carry`). The hint is never applied.

For options use [`verify --options`](options.md). Every profile below ships two or more traps (a flawed strategy the
verifier must flag) and two honest controls (a strategy it must not flatter or wrongly accuse); the tests run them all.

Profiles are provisional, like the [ARL](arl.md) rules. They describe verification coverage. They are not investment advice.

<!-- profiles:start -->
### `trend_cta`: Trend following / CTA

Time-series momentum on one or many instruments, long and short, usually with volatility targeting.

- **Benchmark:** Buy-and-hold of the same instrument(s); beta-neutral residual
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `alpha_after_beta`, `benchmark`, `timing_significance`, `regime_stability`, `delay_sensitivity`, `cost_sensitivity`, `walk_forward_stability`
- **Recommended checks:** `rebalance_timing_luck`, `parameter_plateau`, `regime_swap_null`
- **Metrics to read:** net Sharpe, alpha after beta, max drawdown, time under water, Sharpe at doubled costs

| Not assessed | Why |
|---|---|
| Roll and carry on futures | no continuous-contract roll data is read from OHLCV; a spliced back-adjusted series hides roll cost |
| Crisis behaviour outside the sample | one history cannot show the next crisis |

| Trap | What it does | Expected |
|---|---|---|
| `centered_window` | A trend filter with a centred moving average reads bars after the decision. | a lookahead check fails |
| `whipsaw_overtrade` | Flipping position every bar looks active but costs eat the edge. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `mean_reversion`: Mean reversion

Fades short-term moves back to a mean (z-score, RSI, Bollinger style) on one instrument or a basket.

- **Benchmark:** Random entry with matched holding time
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `timing_significance`, `cost_sensitivity`, `delay_sensitivity`, `cost_realism`, `period_consistency`
- **Recommended checks:** `capacity`, `regime_stability`, `tail_dependence`
- **Metrics to read:** win rate vs payoff, left tail, net Sharpe, break-even cost bps, worst day

| Not assessed | Why |
|---|---|
| Ruin through averaging down | a short sample rarely contains the sequence that ends the account |
| Fill quality at extremes | spreads widen when a z-score is extreme; only quotes can show it |

| Trap | What it does | Expected |
|---|---|---|
| `full_sample_zscore` | Z-score from the mean and deviation of the whole file uses the future. | a lookahead check fails |
| `overtrade` | High-turnover reversion with no cost margin. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `pairs_stat_arb`: Pairs and statistical arbitrage

Trades the spread of two or more related instruments, long one leg and short another.

- **Benchmark:** Zero (self-financing spread); per-leg buy-and-hold
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `structural_break_spread`, `legging_risk`, `borrow_risk`, `pair_selection`, `cost_sensitivity`
- **Recommended checks:** `structural_break_hedge`, `spread_half_life`, `accounting_mismatch`
- **Metrics to read:** spread half-life, hedge-ratio stability, Sharpe after legging delay, pairs screened

| Not assessed | Why |
|---|---|
| Borrow availability and recall | needs a borrow history the verifier does not have; a fee and an unavailable share can be declared |
| Corporate events on one leg | declared actions only; no event feed is read |

| Trap | What it does | Expected |
|---|---|---|
| `future_hedge_ratio` | A hedge ratio fitted on the whole file uses the future. | a lookahead check fails |
| `pair_overtrade` | Spread flips every bar: cost eats the convergence. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `carry`: Carry (spot and perpetual, futures basis)

Earns a yield difference such as funding or basis while holding offsetting positions.

- **Benchmark:** Spot buy-and-hold; cash
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `carry_decomposition`, `carry_margin`, `funding_borrow_stress`, `capacity`, `cost_sensitivity`
- **Recommended checks:** `carry_margin_no_topup`, `carry_future_probe`, `regime_stability`
- **Metrics to read:** carry per year, funding share of P&L, margin utilisation, drawdown in a squeeze, break-even funding

| Not assessed | Why |
|---|---|
| Exchange default and withdrawal risk | counterparty events are not in price data |
| Basis blow-out in a crisis | only the sample's worst bars are seen |

| Trap | What it does | Expected |
|---|---|---|
| `funding_known_early` | Position decided with the next bar's funding or price. | a lookahead check fails |
| `carry_overtrade` | Entering and leaving the pair every bar pays both legs' costs each time. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `cross_sectional`: Cross-sectional long-short (factor, momentum, equity L/S)

Ranks many instruments each period and goes long the top, short the bottom.

- **Benchmark:** Market and factor regressions; equal-weight universe
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `alpha_after_beta`, `selection_vs_timing_basket`, `survivorship`, `universe_membership`, `rebalance_timing_luck`
- **Recommended checks:** `publication_dates`, `execution_capacity`, `funding_borrow_stress`
- **Metrics to read:** alpha after beta, turnover, long vs short leg, breadth, capacity

| Not assessed | Why |
|---|---|
| Point-in-time fundamentals and constituents | no point-in-time database is shipped: the universe must be supplied as it was |
| Short availability | borrow history is not available; a fee and an unavailable share can be declared |

| Trap | What it does | Expected |
|---|---|---|
| `future_rank` | Ranking against the whole-sample mean uses the future. | a lookahead check fails |
| `rank_overtrade` | Daily full re-ranking with no cost margin. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `buy_and_hold`: Buy-and-hold / passive

Holds an asset or index; the null every active strategy must beat after costs and risk.

- **Benchmark:** Itself; the matching total-return index
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `benchmark`, `regime_stability`, `corporate_actions`, `data_quality`
- **Recommended checks:** `survivorship`, `period_consistency`
- **Metrics to read:** CAGR, volatility, max drawdown, time under water

| Not assessed | Why |
|---|---|
| Whether the sample is representative | history is one draw |
| Tax drag and index substitution | not modelled |

| Trap | What it does | Expected |
|---|---|---|
| `peek_entry` | Buying only before up days looks like a passive hold but reads tomorrow. | a lookahead check fails |
| `hold_overtrade` | A 'passive' book that trades every bar is not passive. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `always_flat` | Never trades: nothing to verify, so no pass level may be reached. | verdict is not PASS |
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |

### `allocation_risk_parity`: Allocation and risk parity

Fixed or risk-based weights across sleeves (60/40, inverse volatility, equal risk contribution, minimum variance).

- **Benchmark:** 60/40 and 1/N at matched volatility
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `benchmark`, `rebalance_timing_luck`, `regime_stability`, `correlation_breakdown_stress`, `cost_sensitivity`
- **Recommended checks:** `tail_dependence`, `capacity`, `pbo`
- **Metrics to read:** volatility vs target, leverage used, risk contribution, drawdown in a correlation flip

| Not assessed | Why |
|---|---|
| Cost and availability of the leverage | financing terms are a declared input, not observed |
| Future stock-bond correlation | regimes change sign across eras |

| Trap | What it does | Expected |
|---|---|---|
| `future_covariance` | Weights from the covariance of the whole file use the future. | a lookahead check fails |
| `alloc_overtrade` | Re-weighting every bar creates turnover the allocation does not need. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `market_neutral`: Market-neutral

Aims at zero market exposure: long and short books of similar size, or hedged with an index.

- **Benchmark:** Zero; the market (beta must be near 0)
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `alpha_after_beta`, `selection_vs_timing_basket`, `tail_dependence`, `correlation_breakdown_stress`, `cost_sensitivity`
- **Recommended checks:** `funding_borrow_stress`, `execution_capacity`, `regime_stability`
- **Metrics to read:** beta to the market, alpha t-stat, drawdown in a factor crash, gross vs net exposure

| Not assessed | Why |
|---|---|
| Hidden factor exposure | only the benchmark and reference asset passed in are tested |
| Crowding and de-grossing events | not visible in price history |

| Trap | What it does | Expected |
|---|---|---|
| `future_hedge` | The hedge is sized with the whole sample. | a lookahead check fails |
| `neutral_overtrade` | Rebalancing the hedge every bar costs the whole edge. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `short_volatility`: Short volatility and tail selling

Collects a premium for selling insurance: small steady gains, rare large losses.

- **Benchmark:** Equity index; put-write index
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `hidden_short_volatility`, `implausible_consistency`, `return_smoothing`, `drawdown_consistency`, `regime_stability`
- **Recommended checks:** `tail_dependence`, `correlation_breakdown_stress`, `liquidity_stress`
- **Metrics to read:** skew, worst day and worst month, CVaR, time to recover, Sortino vs Sharpe

| Not assessed | Why |
|---|---|
| Margin calls in a spike | needs the margin rules of the broker |
| The next vol event | Feb 2018 and Mar 2020 style events are only tested when they are in the file |

| Trap | What it does | Expected |
|---|---|---|
| `smooth_tail` | A book that avoids the loss days by reading tomorrow looks like a smooth premium. | a lookahead check fails |
| `premium_overtrade` | Constant trading is not a premium; costs eat it. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `event_driven`: Event-driven (earnings, merger arbitrage, announcements)

Trades around dated events: earnings, announcements, mergers, macro releases.

- **Benchmark:** Market plus risk-free; matched non-event periods
- **Required checks:** `data_integrity`, `lookahead_truncation`, `repaint_history`, `net_profitability`, `deflated_sharpe`, `trials_disclosed`, `pit_events`, `publication_dates`, `timing_significance`, `cost_sensitivity`, `delay_sensitivity`
- **Recommended checks:** `events_quality`, `capacity`, `survivorship`
- **Metrics to read:** event-window return, hit rate, time from publication to fill, deal-break loss

| Not assessed | Why |
|---|---|
| Event data quality | timestamps must be publication times: only a supplied table can be joined by publication time |
| Deal-break tail | a short sample has few breaks |

| Trap | What it does | Expected |
|---|---|---|
| `event_time_join` | Acting on the event period end instead of its publication time reads the future. | a lookahead check fails |
| `event_overtrade` | Trading every bar around an event window pays costs for noise. | verdict REJECT |

| Honest control | What it is | Expected |
|---|---|---|
| `random_entry` | Random entries on random prices: no edge exists, so no pass level may be reached. | verdict is not PASS; no lookahead check fails |
| `honest_causal` | A causal moving-average rule on random prices: not flagged for look-ahead, and no edge claimed. | verdict is not PASS; no lookahead check fails |

### `options`: Options (long and short premium, spreads)

Trades listed options: the table of trades with quotes, and when known the volatility used, the underlying price and the dates.

- **Benchmark:** Underlying and a put-write or covered-call index at matched risk
- **Required checks:** `bid_ask_fill`, `iv_asof`, `tail_stress`, `early_exercise_pin`, `margin_simplified`, `dividends`
- **Recommended checks:** `options_chain`
- **Metrics to read:** P&L at the touch vs at the mid, stress loss share of equity, net dollar gamma, peak margin share of equity, short options near expiry

| Not assessed | Why |
|---|---|
| Historical volatility surface and skew as of each date | no historical option chain is read; only the volatility the table says was used |
| Liquidity, open interest and tradable strikes | not in a trade table |
| Exact margin and assignment | broker rules differ; the margin is a simplified Reg-T style estimate and assignment is a warning |

| Trap | What it does | Expected |
|---|---|---|
| `mid_fill` | Every trade fills at the mid of a wide spread: the profit disappears at the touch. | `bid_ask_fill` is fail |
| `iv_from_future` | The volatility used was observed after the decision date. | `iv_asof` is fail |
| `smooth_tail_sale` | Far out-of-the-money puts sold for steady small gains: a -20% move with volatility x2 wipes out the account. | `tail_stress` is fail |

| Honest control | What it is | Expected |
|---|---|---|
| `touch_fills_hedged` | Fills at the touch, point-in-time volatility, a defined-risk spread: none of the three trap checks fails. | none fails: `bid_ask_fill`, `iv_asof`, `tail_stress` |
| `no_quotes` | A table with no quotes, no volatility and no underlying: every check is reported as not assessed and the verdict is not PASS. | verdict is not PASS; not assessed: `bid_ask_fill`, `iv_asof`, `tail_stress` |
<!-- profiles:end -->
