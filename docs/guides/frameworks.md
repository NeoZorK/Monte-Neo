# Use Monte-Neo with your framework

Monte-Neo does not replace your backtesting framework. Run the backtest where you always do, then hand
the result to the verifier. It re-simulates the positions with its own costs and runs the economic
and statistical checks.

Without strategy code the verifier cannot run the look-ahead probes or the lint, and the certificate says
so. If you have the strategy function, also verify it with `--strategy` (or `signal_fn=`).

## Timing convention

The verifier reads the position at bar `t` as "decided at the close of `t`, filled at the open of `t + 1`".
A framework that fills at the open of bar `t` therefore enters the position array at `t - 1`. A framework
that fills at the close of bar `t` (Nautilus on bar data, bt) enters it at `t`. Reading a close fill as an
open fill would put every position one bar too early, and the verifier would see one bar of the future: the
adapters below set this per framework, and `from_fills(..., fill_at="open" | "close")` lets you say it for any other.

## Adapters

```python
from monte_neo.verify import (
    from_vectorbt, from_backtrader, from_backtesting_py, from_bt, from_nautilus,
    from_zipline, from_freqtrade, from_lean, from_fills,
)

report = from_vectorbt(pf["BTC"]).verify()                        # a vectorbt Portfolio, one column
report = from_backtrader(strat.analyzers.tx.get_analysis(), "prices.csv").verify()
report = from_backtesting_py(stats, "prices.csv").verify()        # Backtest(..., finalize_trades=True)
report = from_bt(result, "prices.csv").verify()                   # bt: security weights
report = from_nautilus(engine, "prices.csv").verify()             # BacktestEngine or its fills report
report = from_zipline(transactions, "prices.csv").verify()
report = from_freqtrade(trades_df, "BTC_USDT-1h.feather").verify()
report = from_lean(order_events, "spy_hour.csv").verify()
report = from_fills(fills_df, "prices.csv", fill_at="open").verify()   # any other framework
```

Every adapter returns an `Adapted` object with `.ohlcv`, `.positions` and `.verify(**kwargs)`. The keyword
arguments are those of `verify_strategy` (`model=`, `n_trials=`, `claim=`, ...).

| Function | Input | Positions | Fills read as | Checked against |
|----------|-------|-----------|---------------|-----------------|
| `from_vectorbt(pf)` | a `Portfolio` with one column (`pf["BTC"]`) | weight of equity: `assets x close / value` | (weights) | the real framework |
| `from_backtrader(tx, ohlcv)` | `bt.analyzers.Transactions` analysis, or a list of `{timestamp, quantity}` | sign of the running size | open | the real framework |
| `from_backtesting_py(stats, ohlcv)` | `stats` of `Backtest.run()` | sign of the running size | open | the real framework |
| `from_bt(result, ohlcv)` | `result.get_security_weights()` of one security | the weights | (close: weight on `t` is decided at `t`) | the real framework |
| `from_nautilus(engine, ohlcv)` | `BacktestEngine`, or `generate_order_fills_report()` | sign of the running quantity | close (`fill_at="close"`) | the real framework |
| `from_zipline(tx, ohlcv)` | flat list of `{dt, amount}` | sign of the running amount | open, on the session date | the real framework |
| `from_freqtrade(trades, ohlcv)` | trades of one pair: `open_date`, `close_date`, `is_short` | +1 / -1 while a trade is open | open | fake trade tables only |
| `from_lean(events, ohlcv)` | order events: `time`, `fillQuantity`, `status` | sign of the running fill quantity | open | fake events only |
| `from_fills(fills, ohlcv, fill_at=)` | `timestamp`, signed `quantity` | sign of the running quantity | your choice | unit tests |

"The real framework" means a CI job runs a moving-average strategy in the installed framework and compares the
adapter's positions with the position the framework itself held on every bar (`tests/frameworks`). Freqtrade and Lean
are not in that job (Freqtrade needs exchange access to start, Lean runs in Docker): check their adapters on your
own run before trusting a certificate, and tell us the result.

Notes from those runs: Backtrader and backtesting.py fill at the next open; backtesting.py leaves a trade that is
still open at the last bar out of its `_trades` unless you pass `finalize_trades=True`; Zipline stamps a daily
transaction with the session close time, so the adapter uses its date; the Nautilus data wrangler needs pandas below 3.

## Jupyter

`verify_strategy` and `verify_grid` return a `Certificate`: a normal `dict` that draws the HTML report when
it is the last value of a notebook cell. Printed on its own it shows one summary line (`<Certificate REJECT aaa517d7cfc1ec16: 24 checks, 3 failed>`); the data is unchanged (`report["checks"]`, `dict(report)`, `json.dumps(report)`). The report sits in a sandboxed frame, so notebook and report styles do
not mix. A certificate loaded from a JSON file is shown with `monte_neo.verify.show(cert)`.

```python
report = from_vectorbt(pf["BTC"]).verify()
report            # the report appears in the cell
report.save_html("report.html")
```

## pandas accessor

```python
import monte_neo.verify.accessor            # registers df.monte_neo

df.monte_neo.verify(positions_array)
df.monte_neo.verify(strategy=my_signal_function)
```

## pre-commit

Fail a commit when a strategy file contains a look-ahead pattern (`shift(-1)`, centred windows, whole-sample
fits, shuffled splits, ...):

```yaml
repos:
  - repo: https://github.com/NeoZorK/Monte-Neo
    rev: v0.51.0
    hooks:
      - id: monte-neo-lint
```

By default the hook checks every Python file. A data-preparation script may legitimately use `shift(-1)` to build labels, so limit the hook to your strategy files:

```yaml
      - id: monte-neo-lint
        files: ^strategies/
```

The hook runs `monte-neo verify --lint FILE...`. It exits 1 when any file has a fail-level finding and prints
warnings without failing. It reads files only; it does not run them.

## Badge

```bash
monte-neo verify --ohlcv prices.csv --strategy strategy.py --badge badge.json
```

`badge.json` is a [shields.io endpoint](https://shields.io/badges/endpoint-badge) file with the verdict and the
first eight characters of the certificate id. Publish it at a public URL (a file in the repository works) and add
to your README:

```markdown
[![Monte-Neo](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/OWNER/REPO/main/badge.json)](https://neozork.github.io/Monte-Neo/verify/)
```

The badge is a claim you make about your own repository, not a certification by Monte-Neo: keep the certificate
next to it so anyone can run `--recheck`.

## Docker image

Each release is also published as `ghcr.io/neozork/monte-neo-verify` (tags `latest` and the version). It is the
image from [`docker/verify`](https://github.com/NeoZorK/Monte-Neo/tree/main/docker/verify): engines precompiled,
runs as `nobody`, meant for code you do not trust:

```bash
docker run --rm --network none --read-only --tmpfs /tmp \
  -v "$PWD:/work:ro" -w /work ghcr.io/neozork/monte-neo-verify:latest \
  monte-neo verify --ohlcv prices.csv --strategy strategy.py --isolate
```
