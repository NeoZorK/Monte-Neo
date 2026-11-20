# Delta-neutral carry (`verify --carry`)

Carry here means a hedged pair: a long spot position and an equal short perpetual. The price exposure cancels; what is left is the
**funding** the short perpetual receives (or pays) and the **basis** (perpetual minus spot) moving. Not investment advice.

```bash
monte-neo verify --carry table.csv --strategy rule.py --carry-costs 10,5 --carry-capital-apr 0.05 --carry-leverage 3
```

`table.csv` has `timestamp, spot_close, perp_close` and `funding_rate` (the fraction a long pays over that bar) or `funding_bps`.
Add `volume` (dollar volume of the thinner leg) for the capacity estimate. A `symbol` column makes a **basket**: every coin is its own
hedged instrument, `signal(df)` returns one weight per row, and the verifier's portfolio checks apply. `rule.py` defines `signal(df)`
returning 1 (hold the pair) or 0 (flat); `df` has `spot_close`, `perp_close`, `basis`, `funding_rate` and `basis_pnl`.
The funding of a bar is what is settled *over* that bar, so a rule may use it only on later bars.

Per bar the pair earns `spot return - perpetual return + funding`; this series is the instrument the full verifier tests, so
the look-ahead, truncation, cost and significance checks run on the entry rule. Entry and exit pay both legs (`--carry-costs SPOT,PERP`
in bps per fill). `--carry-capital-apr` charges the capital tied up for every bar the pair is held.

## Rules that differ from the generic ones, and why

The rules come from what a carry position earns, and were calibrated on traps and on synthetic honest controls, never on a real candidate.

| Check | Generic rule | Carry rule |
|-------|--------------|-----------|
| `implausible_accuracy` | Share of bars whose next move agrees with the position. | Funding accrues almost every held bar and is mostly positive, so the share of winning bars is high *by construction*. The hit rate is measured on the **basis**, the directional part of the P&L. A rule that peeks at the next basis move still fails. |
| `carry_future_probe` (new) | - | From several bars, the later prices are scaled by noise and the later funding is replaced by its negative plus noise; the table is rebuilt and the signal up to that bar must not move. A rule that reads the funding it is about to earn (`shift(-1)`, the next rate) fails. The generic truncation probe also covers it. |
| `sample_size` | Closed trades against `min_trades`. | The **effective number of independent accrual periods** while held: `n * gamma0 / LRV` from a Newey-West long-run variance of the held-bar returns, never above the number of held bars. Closed trades are shown beside it. A rule needs at least 30 held bars and `min_trades` effective periods. |
| `few_decisions` (new) | - | A **warning** when the rule opened fewer than 10 positions: the accrual sample says nothing about the rule that decides when to hold. It does not substitute for the sample. |
| `data_independence` | Positions must react to unrelated prices. | Positions must react to unrelated *carry inputs*: prices and funding are replaced by their time-reversed copies and the table is rebuilt. A rule that answers the same holds a stored answer. |
| `alpha_after_beta`, regime checks | Benchmark is holding the instrument. | The reference is the **underlying (spot)**: a hedged pair should have no beta to it. For a basket, the equal-weight spot of the coins. |
| `carry_decomposition` (new) | - | Funding P&L against basis P&L over the held bars: a warning when less than half of the profit is funding (a basis bet, not carry) or funding was not earned. |
| `carry_margin`, `carry_margin_no_topup` (new) | - | A margin account of the short perpetual is simulated for every held episode and coin: equity is the initial margin `1/leverage` plus the funding received (negative funding drains it) minus the price rise; the position is **liquidated when the equity at the bar's high** (column `perp_high`; the close only if it is missing, which is said and warns) reaches the maintenance margin. The spot leg is **not** collateral. With no policy nothing is ever added: 5x leverage on a 20 % rise liquidates. A **declared policy** `{"trigger", "delay_bars", "cost_bps"}` tops up to `1/leverage` when equity falls below `trigger` of the notional; the transfer arrives `delay_bars` later (the bar can liquidate in between) and costs `cost_bps` of the amount moved. A policy that does not arrive in time for a gap fails; one that survives only by adding cash warns with the reserve needed; `carry_margin_no_topup` always shows what happens with no management. |

The certificate hash covers the spot, perpetual and funding columns, not only the hedged index.

## Attribution, survivorship, capacity, independence

* **`residual_alpha`, `hidden_short_volatility`** are computed for the carry returns against the underlying (`--carry-reference COIN` for a
  basket, with the equal-weight spot as a second factor), so ARL level 5 is assessed. Carry is a short-volatility position by nature, so the
  second row also reports the funding paid on held bars when funding turns negative and the worst basis bar, and warns when negative funding
  takes back half of what funding earned.
* **Survivorship cap.** A hand-made list of coins keeps the cap at ARL 4, even when it is declared complete (`delisted=[]`). Only an
  **ex-ante composition rule** the verifier recomputes lifts it: `--carry-universe-rule '{"top_n": 10, "lookback_bars": 90, "rebalance_every": 90, "on": "perp_quote_volume"}'`.
  On each rebalance bar the verifier takes the top coins by that volume over the bars strictly before it; the column `in_universe` is added to the
  table, positions outside it fail the row `universe_rule`, and the cap is lifted only if coins of the pool also stop trading inside the sample
  (a pool in which every coin lives from the first to the last bar is a list of survivors, whatever the rule).
* **Capacity.** One formula: the capital a fill may use is `min(spot quote volume, perpetual quote volume) x participation share` over the bars the
  order may be spread over (`--carry-spread-bars`, default 1 = the fill bar only), divided by the weight change. Volumes are traded value in
  quote currency (USDT), per bar, never base units and never multiplied by the hedged index. The generic capacity check multiplies volume by the
  close, and the close of a carry table is the hedged index (about 100), so a volume given as quote value was inflated by that index; the table
  now divides it out. A daily figure from 8-hour bars is about three bars of volume: use `--carry-spread-bars 3` to compare with "1 % of the day".
  Inputs: `spot_quote_volume` and `perp_quote_volume`, or `volume` as the quote value of the thinner leg.
* **`data_independence`** runs for a basket too: prices and funding of every coin are replaced by time-reversed copies and the table is rebuilt.

## What is checked elsewhere in the run

* **Rebalance phase:** pass `rebalance_every` (the cadence of the rule in bars) and the generic `rebalance_timing_luck` row reports the worst phase.
* **Capacity:** with a `volume` column the capacity row prices the size of the position against the traded volume.
* **Funding paid on top of carry** (a perpetual leg of a long-short portfolio rather than a hedged pair) is `alpha --funding`, see the research guide.

## What it does not do

It does not model exchange outages, the delay of funding settlement, auto-deleveraging or basis in the spot leg of a margin account.
The margin check is a path check on the perpetual price, not a margin engine.
