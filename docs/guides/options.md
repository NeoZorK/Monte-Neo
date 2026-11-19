# Options verification

`monte-neo verify --options trades.csv` checks a table of option trades. It is built for the ways option backtests lie:
fills at the mid of a wide spread, volatility from the future, steady premium that hides a tail, and assignment, margin and
dividends that the backtest ignored.

```bash
monte-neo verify --options trades.csv --equity 100000 --out options_cert.json
```

## Input

One row per trade. Required columns: `date`, `expiry`, `right` (C or P), `strike`, `qty` (positive bought, negative sold),
`fill_price`. Optional columns turn on more checks:

| Column | Used by |
|---|---|
| `bid`, `ask` | `bid_ask_fill`: P&L at the touch against the reported P&L |
| `exit_price`, `exit_date`, `exit_bid`, `exit_ask` | realised P&L, open-position windows |
| `underlying_price`, `iv_used` | `tail_stress`, `margin_simplified` |
| `iv_asof` | `iv_asof`: date the volatility was observed |
| `ex_div_date`, `dividend`, `style`, `underlying_at_expiry` | `dividends`, `early_exercise_pin` |
| `multiplier` (default 100), `symbol` | all |

## Checks

| Check | What it asks |
|---|---|
| `bid_ask_fill` | Does the profit survive when buys fill at the ask and sells at the bid? Fills better than the mid fail. |
| `iv_asof` | Was every volatility observed on or before the decision date? |
| `tail_stress` | What does the open book lose with the underlying -20 % or +20 % and volatility doubled (Black-Scholes reprice)? With `--equity`, more than 50 % of equity fails and more than 20 % warns. Also reports net dollar gamma. |
| `early_exercise_pin` | Short American options across an ex-dividend date, deep in the money, or expiring near the strike: warnings. |
| `margin_simplified` | Peak margin of the short options, Reg-T style, against equity. Broker and portfolio margin differ. |
| `dividends` | Short calls held across an ex-dividend date with no dividend amount. |
| `options_chain` | Always listed: a historical chain is not read. |

## Not assessed

A check whose input is missing is reported as `skip` with "not assessed" and the reason; the verdict then cannot be PASS
(at best NEEDS_MORE_EVIDENCE). Without a historical option chain, the volatility surface as of each date, tradable strikes
and open interest are not assessed, whatever the verdict says. The stress model is European Black-Scholes with the
volatility the table gives: it is a stress, not a quote.

The options profile is part of [strategy-type profiles](profiles.md): its traps (mid-fill, volatility from the future,
selling the tail with a smooth curve) and honest controls are tested. Results are not investment advice.
