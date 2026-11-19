# Gates: alpha after beta, cost realism, market regimes

These rows are part of `verify_strategy` (and `alpha_after_beta` also of `verify --returns --benchmark`).

| Row | Question | Warn / fail when |
|-----|----------|------------------|
| `alpha_after_beta` | Is the return more than exposure to buy & hold? | The 95% interval of annual alpha (Newey-West) includes zero. The ARL then stops at level 4 ("beta is not new alpha") |
| `cost_sensitivity` | Does the edge survive doubled costs? | Profitable at modeled costs, not at 2x |
| `cost_realism` | Are modeled costs below the real spread? | Profit disappears at fee + half-spread: `fail` with real quotes (`quotes_half_spread_bps`), `warn` with the noisy high-low estimate |
| `regime_stability` | Is the evidence from one regime? | A regime has under 10% of the bars, the strategy loses in a regime holding 20% or more, or one regime earns over 90% of the profit |

| `rebalance_timing_luck` | Does the result depend on the day the portfolio is rebalanced? | The worst phase (delays 0..k-1) loses money, or best-worst exceeds half of the mean; the worst phase is the headline |
| `selection_vs_timing_basket` | Is a basket's profit stock selection or market timing? | Over 80% of the mean P&L is net exposure times the equal-weight market, and selection is not significant |
| `alpha_after_reference` | Alpha after the basket and a reference asset (`reference_symbol`) | Alpha is not significantly positive after both betas |

## Cost profiles

```python
from monte_neo.verify import verify_strategy
from monte_neo.verify.cost_profiles import quotes_half_spread_bps

half = quotes_half_spread_bps(quotes["bid"], quotes["ask"])["half_spread_bps"]
verify_strategy(ohlcv, strategy="s.py", cost_profile="binance_usdm_vip1", maker_share=0.3, quotes_half_spread_bps=half)
```

`cost_profile` is a name from `FEE_PROFILES` or a `(maker, taker)` pair in bps per side. The built-in figures are for
orientation only: check the exchange's live schedule. `maker_share` defaults to 0 (all fills pay taker).

## What these gates do not cover

Regime labels use only the trailing return and volatility of the data you give; they are not a model of macro regimes.
Alpha is measured against buy & hold of the same data, not against a factor model.
