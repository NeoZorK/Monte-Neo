# Validation dossier, Alpha Readiness Level and live monitoring

Three tools for the steps after a backtest is verified: putting it before a committee, saying where it stands on the
way to capital, and watching it once it trades.

## `monte-neo dossier`: one folder for a committee, a validator or an auditor

```bash
monte-neo dossier --demo --framework sr11-7                 # no files
monte-neo verify --ohlcv data.csv --strategy s.py --out cert.json
monte-neo dossier --certificate cert.json --framework ss1-23 --name "Momentum 20" --owner "Desk A" \
  --purpose "Daily futures overlay" [--alpha alpha.json] [--live live.json] --out dossier/
```

The folder holds:

- `dossier.html`, one page with no scripts and no network, printable to PDF: the verdict, purpose and scope, the
  results, every check, the Alpha Readiness Level, the framework map, the assumptions and limitations, how to
  reproduce, and blank sign-off fields;
- `dossier.json` (`validation-dossier/1`), the certificate itself, `environment.json` (Python, platform, package
  versions), `REPRODUCE.md` (the exact command and the expected certificate id) and `limitations.md`.

Frameworks (`--framework`):

| Name | Framework |
|------|-----------|
| `generic` | Data, look-ahead, economics, statistics, claims, policy, reproducibility, monitoring |
| `sr11-7` | Federal Reserve SR 11-7 / OCC 2011-12, model risk management |
| `ss1-23` | PRA SS1/23, model risk management principles for banks |
| `rts6` | MiFID II RTS 6 (Delegated Regulation 2017/589), testing of algorithms |

The map shows, per clause, whether the dossier holds **evidence** for it (`covered`, `partial`, `not covered`) and what
that evidence says. Clauses that need a person, such as conceptual soundness or governance, are never shown as fully
covered. **A dossier is evidence for a validation, not a statement that anyone complies with a framework.**

MCP tool: `build_dossier`.

## Alpha Readiness Level (ARL 1–9)

Every `alpha` report and every dossier carries an ARL: where the evidence stands on the way from an idea to capital.

| ARL | Level | Evidence |
|-----|-------|----------|
| 1 | Idea on clean data | `data_integrity`, or an aligned scores panel |
| 2 | The backtest is not broken | look-ahead probes, or universe look-ahead; **any** failed look-ahead check stops here |
| 3 | It earns after costs | `net_profitability`, or `market_impact` at your `--aum` |
| 4 | The signal predicts | `ic` and `signal_placebo`, or `timing_significance` |
| 5 | It is new alpha | `residual_alpha` (t ≥ 3 after factors) and no `hidden_short_volatility` |
| 6 | It survives the search | `deflated_sharpe`, or the t ≥ 3 hurdle with enough history |
| 7 | Tradable and robust | impact or capacity; synthetic markets, subsets and start dates (or period consistency and delays); rebalance day (or cost margin) |
| 8 | It adds to your book | `marginal_sharpe` with `--book` |
| 9 | Confirmed live | `live_vs_backtest` and `alpha_death_monitor` |

The level is the highest one met together with every level below it. Missing evidence is **not assessed**, never
passed, and the report names the run that would produce it, for example
`ARL 6/9 — blocked at 7: tradable and robust (rebalance_timing_luck)`.

The ARL rates the evidence, not the investment.

## `monte-neo monitor`: after launch

```bash
monte-neo monitor --certificate cert.json --live live.csv [--fills fills.csv] [--haircut 0.5] [--out live.json]
```

`live.csv` has live or paper returns (date, return). `fills.csv` has timestamp, symbol, side, quantity, price and,
for slippage, the decision price `reference_price`.

| Check | What it says |
|-------|--------------|
| `live_vs_backtest` | Correlation, tracking error and the mean difference against the backtest on the same dates |
| `implementation_shortfall` | Realised slippage against the modelled one, and the value to use instead |
| `alpha_death_monitor` | Sequential alarms (CUSUM, SPRT) against the backtest edge shrunk by `--haircut`, with the date of the alarm |
| `live_track_needed` | How much live history is still needed to tell the edge from zero |

Exit code 0 means no warning and 2 means a warning, so it can run from cron or CI. MCP tool: `monitor_live`.

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not
predict future returns.
