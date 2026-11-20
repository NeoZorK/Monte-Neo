# Econometric checks for pairs and stat-arb strategies

`verify --legs` asks whether the reported P&L is what the legs earned (see [phantom profit](phantom-profit.md)). It does
not ask whether the pair has a relationship worth trading. `--pairs-checks` adds that: cointegration, the half-life of the
spread, the stability of the hedge ratio, structural breaks, pair-selection bias, and the cost of a late second leg or a
short that cannot be borrowed.

```bash
monte-neo verify --legs legs.csv --pairs-checks --pairs-tested 45 --legging-delay 1 --borrow-bps 300 --out cert.json
```

The input is the same legs table as for `--legs` (`date`, `px_<leg>`, `qty_<leg>`, `reported_return`). The first two legs
form the tested pair; with three or more legs the Johansen test runs on all of them (at most five). Agents call the MCP
tool `verify_pairs`. The certificate is `strategy-verdict/1`; without `--pairs-checks` it is unchanged.
With it, extra check rows are appended and `reproducibility.settings.pairs` records the options.

## How the verdict is affected

An honest pair must never be rejected for its econometrics alone, so the checks are graded like this:

| Check | Category | Worst status | Effect on the verdict |
|---|---|---|---|
| `cointegration_eg`, `cointegration_johansen` | statistics | fail | `NEEDS_MORE_EVIDENCE` |
| `spread_half_life`, `hedge_ratio_stability`, `rolling_cointegration` | statistics | warn | `PASS_WITH_WARNINGS` |
| `structural_break_spread`, `structural_break_hedge` | statistics | fail | `NEEDS_MORE_EVIDENCE` |
| `chow_known_date` | statistics | warn | `PASS_WITH_WARNINGS` |
| `pair_selection` | statistics | fail | `NEEDS_MORE_EVIDENCE` |
| `legging_risk`, `borrow_risk` | economics | warn | `PASS_WITH_WARNINGS` |

`REJECT` still comes only from the integrity and economics failures that existed before (`accounting_mismatch`).

## Cointegration

* **Engle-Granger** (`cointegration_eg`): regress `log y` on `log x`, test the residual for a unit root with ADF (constant,
  lag by AIC). The residual is estimated, so the ordinary ADF table does not apply; the 1 / 5 / 10 % critical values are
  the asymptotic MacKinnon (2010) values for two series, -3.896 / -3.336 / -3.044. The row gives the statistic, the
  p-value bucket and the hedge ratio. The p-value is a bucket, not a number, on purpose: the table is asymptotic.
* **KPSS** is run on the same spread with the opposite null (the spread is stationary). The row passes when Engle-Granger
  rejects a unit root at 5 % and KPSS does not reject stationarity at 5 %; it warns when they disagree or when only the 10 %
  level is reached, and fails when there is no evidence at 10 %. The standalone ADF test uses the MacKinnon (1994)
  p-value surface (check: the 5 % critical value -2.8621 gives p = 0.0500).
* **Johansen** (`cointegration_johansen`, three or more legs): trace test with an unrestricted constant and one lagged
  difference, 95 % critical values of MacKinnon, Haug and Michelis (1999). The row reports the rank and the first
  cointegrating vector.
* **Half-life** (`spread_half_life`): from `ds = a + b s dt + e`, `ln 2 / -ln(1 + b)` bars. It warns when the spread does
  not revert, or when the half-life exceeds a tenth of the sample (few reversions observed).
* **Hedge-ratio stability** (`hedge_ratio_stability`): OLS hedge ratio in sliding windows; warns when the standard
  deviation of the ratio exceeds 25 % of its median.
* **Rolling cointegration** (`rolling_cointegration`): Engle-Granger in sliding windows; warns when fewer than 60 % of the
  windows reject at 5 %, and names the end of the last window that did. The window defaults to a quarter of the sample, at
  least 250 bars (`--pairs-window`). Overlapping windows make this a diagnostic, not a joint test.

## Structural breaks

The tests act on a stationary series, so they are applied to the Engle-Granger spread (`structural_break_spread`) and to
the spread with the hedge ratio **frozen on the first half of the sample** (`structural_break_hedge`). The second asks
the practical question: does the relationship estimated early still hold afterwards? Every statistic is scaled by an AR(1)
pre-whitened long-run variance; scaling by the plain variance would flag nearly every honest pair, because spreads are
autocorrelated.

* **OLS-CUSUM** (Ploberger and Kramer 1992), critical values 1.2238 / 1.3581 / 1.6276 at 10 / 5 / 1 %.
* **Sup-Wald** over an unknown date with 15 % trimming (Quandt 1960; Andrews 1993; Bai and Perron 2003): 7.04 / 8.58 / 12.29.
* **Bai-Perron, simplified**: sequential splitting for up to three more breaks, with the sequential critical values. It is
  not the global dynamic-programming search; the dates are listed in the row's details.
* **Chow test** at a date you give (`--break-date`), as a Wald statistic against chi-square(1).

The row **fails** only when CUSUM and sup-Wald both reject at 1 % and the shift is at least one standard deviation; it
**warns** when either rejects at 5 %. A failing row names the date: "the relationship changed around 2024-03-03 12:00:00".
When the spread drifts after the break (a changed hedge ratio does that), the fitted step lands in the middle of the drift;
the date reported is moved back to the bar where the series first left the early range.

## Pair-selection bias

Screening `N` assets tests `N (N - 1) / 2` pairs, and each pair is often tried with several windows and thresholds. With
`--pairs-tested` (and `--pair-variants`) the Deflated Sharpe (Bailey and Lopez de Prado 2014) of the re-derived returns is
computed with `pairs x variants` trials. The row shows the value for this pair alone next to the deflated one, so the cost
of the selection is visible. Without `--pairs-tested` the row is informational and the Sharpe ratio is not deflated.

## Legging and borrow risk

A backtest fills both legs at one instant. `legging_risk` re-prices the legs table with every leg after the first one
delayed: a delay of `d = k + f` bars holds the old quantity for the fraction `f` of the bar after `k` whole bars. Give the
delay in bars (`--legging-delay`) or milliseconds (`--legging-delay-ms`; the bar length is read from the dates). The row
scans 0, 0.25, 0.5, 1 and 2 bars and the latencies of the arrival-time module (5 to 250 ms) that are at least 0.001 bar,
reports the P&L change and the change of its standard deviation (the risk of the naked leg), and warns when the P&L falls
by more than 30 % or turns into a loss at the test delay (1 bar by default).

`borrow_risk` appears with `--borrow-bps` (an annual fee on the short notional) and `--borrow-unavailable` (the share of
bars, drawn at random with a fixed seed, where no short can be held: those bars' short quantities are zero and the long leg
stays unhedged). Both rows are `skip` when the legs do not earn a profit to begin with.

## What this does not do

* The relationship tests are in-sample by construction. A pass says the spread was stationary in the sample, not that it
  will stay so; the frozen-hedge and rolling rows are the out-of-sample hints.
* Critical values are asymptotic. With a few hundred bars the tests are only approximate; the checks need at least 120 bars.
* Only the first two legs enter the pair tests. Johansen covers up to five legs, and its vector is a diagnostic, not a
  hedge you should trade without the accounting check.
* The legging model changes quantities in time; it does not model partial fills, price impact or the spread widening while
  the second order waits. The borrow model has no recall or locate-cost dynamics.
* Passing these checks does not show that the strategy has an edge. Not investment advice.

## Tests and sources

The math is tested on processes with a known answer (cointegrated pairs, independent random walks, level shifts), including
the size of each test on null data. Sources: Engle and Granger (1987); Dickey and Fuller (1979); MacKinnon (1994, 2010);
Kwiatkowski, Phillips, Schmidt and Shin (1992); Johansen (1988, 1991); MacKinnon, Haug and Michelis (1999); Ploberger and
Kramer (1992); Andrews (1993); Andrews and Monahan (1992); Bai and Perron (1998, 2003); Bailey and Lopez de Prado (2014).
