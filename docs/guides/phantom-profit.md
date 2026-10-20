# Phantom profit in pairs and spread strategies

A pairs or stat-arb backtest often defines the spread with a hedge ratio that is re-estimated on a rolling window, and
books the profit as the position times the change of that spread:

```python
spread = y - beta * x - alpha                  # beta, alpha re-fitted every bar
pnl = position.shift(1) * spread.diff()        # WRONG
```

This looks natural, but `spread[t]` and `spread[t-1]` use different hedge ratios. The portfolio a trader really held
over the bar is one unit of `y` against `beta[t-1]` units of `x`, and it earns

```python
pnl = position.shift(1) * (y.diff() - beta.shift(1) * x.diff())     # RIGHT
```

The difference, `-position * (d_beta * x + d_alpha)`, is the **phantom term**: it comes from re-fitting the hedge and
no trader can earn it. A least-squares refit pulls the new residual towards zero, so the term is aligned with a z-score
position and produces profit from nothing. On independent random walks (pairs with no relationship at all) the wrong
accounting of a standard z-score rule has a median annualised Sharpe ratio between +4 and +15, positive on 100 % of the
pairs, while the same positions booked correctly earn nothing. The artifact is invisible to statistics on the return
series, because the series itself is wrong. The derivation, a simulation that reproduces every number, and the same artifact with exponentially weighted and Kalman hedges are in the preprint "Phantom Mean Reversion" (sources and code in `paper/phantom-mean-reversion/`).

Monte-Neo has two checks for it. Both need the strategy's legs, not only its returns.

## Try it without files

```bash
monte-neo verify --demo-phantom
```

The demo runs one z-score pairs rule on two independent random walks, booked both ways. The wrong booking is REJECTED by
both checks, the right one passes.

## Check 1: re-derive the P&L from the legs (`--legs`)

Export one row per bar with the price and the quantity held in every leg, and the return the backtest reported:

```text
date,px_y,px_x,qty_y,qty_x,reported_return
2024-01-05 05:00:00,101.2,98.7,1.0,-0.83,0.0004
```

- `px_<leg>`: the price at the bar (any number of legs; every leg needs both `px_` and `qty_` columns).
- `qty_<leg>`: the quantity held **over the bar that ends at `date`** (decided at the previous bar), in log-notional units:
  the P&L of a leg is `qty * (log px[t] - log px[t-1])`. With `--legs-pnl simple`, `qty` is a fraction of equity and the
  P&L is `qty * (px[t] / px[t-1] - 1)`.
- `reported_return`: the per-bar return the backtest reports. An optional `cost` column (a per-bar cost already inside
  `reported_return`) is added back before the comparison.

```bash
monte-neo verify --legs legs.csv --legs-fixed-out fixed_returns.csv --out cert.json
```

The check `accounting_mismatch` (integrity) fails, and the verdict is `REJECT`, when more than 5 % of the P&L is not what
the legs earned (`--legs-tol` changes the limit). The measure is `(reported - derived) / max(|reported|, |derived|)` over
the whole record, so a backtest that inflates profit, hides a loss or is shifted by a bar is all found. When the
quantities match the legs better one row earlier, the message says so. `derived_significance` warns when the legs earn too
little to tell from luck. `--legs-fixed-out` writes the returns the legs really earn (`date,return`), the corrected series
to carry forward, for example into `monte-neo verify --returns fixed_returns.csv`.

A runnable example that writes a legs file for one pair of random walks, wrongly and correctly booked:

```bash
python examples/phantom_pairs/make_legs.py legs_buggy.csv buggy
python examples/phantom_pairs/make_legs.py legs_fixed.csv fixed
monte-neo verify --legs legs_buggy.csv     # REJECT, exit code 2: reported Sharpe +8.6, the legs earn -0.4
monte-neo verify --legs legs_fixed.csv     # accounting_mismatch passes, exit code 0
```

## Check 2: the random-walk null test (`--null-test`)

Run the unchanged strategy on pairs of independent random walks of the same length and volatility. A correct strategy earns
nothing there; one that is reliably profitable has a defect in its accounting or data handling, whatever it does on real
data. The test does not need to know the defect.

The strategy is a Python file with a function `pnl(prices)` (name after the colon: `pairs.py:func`). `prices` is a DataFrame
with a column `leg1`, `leg2`, ... of positive prices per leg; the function returns the per-bar return the backtest would
report. The file is imported and run, with the same trust as `--strategy`.

```bash
monte-neo verify --null-test examples/phantom_pairs/pairs_buggy.py:pnl --null-like legs_buggy.csv --periods-per-year 8760
monte-neo verify --null-test examples/phantom_pairs/pairs_fixed.py:pnl --null-like legs_fixed.csv --periods-per-year 8760
```

`--null-like LEGS.csv` takes the length and volatility from a legs file; otherwise `--null-bars` (3000) and `--null-vol`
(0.01) apply. `--null-paths` (100), `--null-legs` (2) and `--null-seed` (7) are the other settings.

Check `edge_on_noise` (economics, a failure is a `REJECT`): it fails when more than 75 % of the paths are profitable and the
median t-statistic of their mean return is above 1, and warns from 65 % / 0.5. With no edge the median t-statistic is near
zero with a standard error of about 0.13 for 100 paths, so both limits are many standard errors away from chance. A pass
means only that no mechanical edge was found on noise; it does not show that the strategy has an edge.

## From an agent

The MCP tool `verify_legs` runs check 1 on a file and returns the same certificate. The rules in `integrations/` tell the
agent to export the legs of a pairs strategy and to fix a `REJECT` by booking the P&L from the legs.

## Scope and honesty

- Both checks are about accounting. Look-ahead in the signal, costs and data quality are checked by the rest of
  `monte-neo verify`; run it as well.
- `--legs` trusts the quantities and prices you export. It finds a reported return that the legs do not earn, not wrong
  quantities.
- The phantom term needs three ingredients: a re-estimated hedge (rolling OLS, exponentially weighted or Kalman), a position
  in the spread and P&L booked from spread changes. Fixed-hedge strategies and strategies booked from legs are not affected.
- Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict
  future returns.
