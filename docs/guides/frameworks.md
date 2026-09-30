# Use Monte-Neo with your framework

Monte-Neo does not replace your backtesting framework. Run the backtest where you always do, then hand
the result to the verifier. It re-simulates the positions with its own costs and runs the economic
and statistical checks.

Without strategy code the verifier cannot run the look-ahead probes or the lint, and the certificate says
so. If you have the strategy function, also verify it with `--strategy` (or `signal_fn=`).

## Timing convention

The verifier reads the position at bar `t` as "decided at the close of `t`, filled at the open of `t + 1`".
A trade that the framework opened at the open of bar `t` therefore enters the position array at `t - 1`.
A framework that fills at the close of `t` is read one bar later than it filled, which is the conservative side.

## Adapters

```python
from monte_neo.verify import from_vectorbt, from_freqtrade, from_lean, from_zipline, from_fills

report = from_vectorbt(pf["BTC"]).verify()                       # a vectorbt Portfolio, one column
report = from_freqtrade(trades_df, "BTC_USDT-1h.feather").verify()
report = from_lean(order_events, "spy_hour.csv").verify()
report = from_zipline(transactions, "prices.csv").verify()
report = from_fills(fills_df, "prices.csv").verify()             # any framework
```

Every adapter returns an `Adapted` object with `.ohlcv`, `.positions` and `.verify(**kwargs)`. The keyword
arguments are those of `verify_strategy` (`model=`, `n_trials=`, `claim=`, ...).

| Function | Input | Positions |
|----------|-------|-----------|
| `from_vectorbt(pf)` | a `Portfolio` with one column (`pf["BTC"]`) | weight of equity: `assets x close / value` |
| `from_freqtrade(trades, ohlcv)` | trades of one pair: `open_date`, `close_date`, `is_short` | +1 / -1 while a trade is open |
| `from_lean(events, ohlcv)` | order events: `time`, `fillQuantity`, `status` | sign of the running fill quantity |
| `from_zipline(transactions, ohlcv)` | flat list of `{dt, amount}` | sign of the running amount |
| `from_fills(fills, ohlcv)` | `timestamp`, signed `quantity` | sign of the running quantity |

### Backtrader and Nautilus

Collect the fills in a list and use `from_fills`. In Backtrader:

```python
class Strategy(bt.Strategy):
    def __init__(self):
        self.fills = []

    def notify_order(self, order):
        if order.status == order.Completed:
            size = order.executed.size          # negative for sells
            self.fills.append({"timestamp": bt.num2date(order.executed.dt), "quantity": size})
```

then `from_fills(strategy.fills, prices).verify()`.

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
    rev: v0.43.1
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
