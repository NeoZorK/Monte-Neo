# Strategy verifier (`monte_neo.verify`)

An independent, deterministic check that runs before anyone trusts a backtest.
It covers three things: look-ahead, trading costs and selection bias.
The result is a `strategy-verdict/1` certificate: a verdict, the checks behind it,
`next_actions` an agent can act on, and SHA-256 hashes that make the run reproducible.

> The verifier checks **methodology**, not future profit. Not investment advice.

## Quick start

```python
from monte_neo.verify import verify_strategy, model_from_costs

report = verify_strategy(
    "btc_1h.csv",                 # open, high, low, close[, timestamp]
    strategy="my_strategy.py",    # defines signal(df) -> positions (+1 / 0 / -1)
    n_trials=40,                  # how many variants you tried before picking this one
    model=model_from_costs(commission_bps=5, slippage_bps=5),
)
print(report["verdict"], report["certificate_id"])
for action in report["next_actions"]:
    print("-", action)
```

You can also pass `signals=` (an array or a `.npy`, `.csv` or `.parquet` file) instead of code.
Positions can be signs (`+1` / `0` / `-1`) or weights (a fraction of equity in `[-1, 1]`, such as
`0.5` or `-0.25`); see [Positions: signs or weights](#positions-signs-or-weights).
Look-ahead probes need code (`strategy=` or `signal_fn=`). With signals alone, only the
statistical smell test runs.

## CLI

```bash
monte-neo verify --ohlcv btc_1h.csv --strategy my_strategy.py --n-trials 40
monte-neo verify --ohlcv btc_1h.csv --signals positions.npy --format json --out verdict.json
monte-neo verify --ohlcv btc_1h.csv --strategy my_strategy.py --html report.html   # HTML report too
monte-neo verify --render verdict.json --html report.html                         # HTML from a certificate
monte-neo verify --schema          # print the JSON schema
```

| Exit code | Meaning |
|-----------|---------|
| 0 | `PASS` or `PASS_WITH_WARNINGS` |
| 1 | `NEEDS_MORE_EVIDENCE` |
| 2 | `REJECT` |
| 3 | Usage or input error (not a verdict) |
| 4 | `--recheck`: the certificate was not reproduced |
| 5 | `--check-signature`: the signature is invalid, or the certificate was signed by a key other than `--public-key` |

## Verdicts

| Verdict | Rule |
|---------|------|
| `REJECT` | Any **integrity**, **lookahead** or **economics** check failed |
| `NEEDS_MORE_EVIDENCE` | Only **statistics** checks failed |
| `PASS_WITH_WARNINGS` | No failures, at least one warning |
| `PASS` | Everything passed |

## Checks

| id | category | fails / warns when |
|----|----------|--------------------|
| `data_integrity` | integrity | NaN, non-positive prices, `high < low`, open or close outside high-low by more than 0.1% (smaller gaps are counted as vendor rounding), timestamps out of order (newest-first data) or duplicated, repeated (timestamp, symbol) rows in a universe (fail, stops the run early) |
| `survivorship` | integrity | universe only: every symbol trades until the last bar, so delisted names are probably missing (warn) |
| `determinism` | integrity | two runs of `signal(df)` on the same data disagree |
| `lookahead_truncation` | lookahead | `signal(df[:t+1]) != signal(df)[:t+1]` at any checkpoint (the whole prefix is compared; checkpoints are spread evenly and also placed where the position changes) |
| `lookahead_perturbation` | lookahead | rewriting bars after `t` (future returns mirrored) changes signals up to `t` |
| `external_data` | lookahead | strategy code (import or `signal()`) reads a data file (`.csv`, `.parquet`, `.npy`…, or the OHLCV file itself) or opens a network connection: the probes rewrite `df` and cannot see data loaded elsewhere |
| `lookahead_static_lint` | lookahead | `shift(-k)`, `center=True`, `bfill`, windows over `x[::-1]`, data loaders (`read_csv`, `np.load`, `open`, network imports) outside `if __name__ == "__main__":` (fail); full-series `fit`/`polyfit`, `rank`, `mean`/`std`/`max`…, group `transform("last")`, `x[i + k]` (warn) |
| `implausible_accuracy` | lookahead | next-bar direction hit rate ≥ 0.70 over ≥ 100 active bars and binomial z ≥ 3.5 (fail); a high rate that is not significant is a warn |
| `costs_modeled` | economics | zero commission and slippage (warn) |
| `net_profitability` | economics | total return ≤ 0 after costs |
| `cost_margin` | economics | break-even cost < 2× the modeled per-side cost (warn) |
| `delay_sensitivity` | economics | profitable, but loses money with one extra bar of execution delay (warn); skip when not profitable |
| `timing_significance` | statistics | the net return does not beat 95% of 200 circular shifts of the same positions (warn): the profit comes from market exposure, not timing; skip when not profitable |
| `sample_size` | statistics | fewer than `min_trades` (default 30) closed trades |
| `deflated_sharpe` | statistics | Deflated Sharpe < 0.5 (fail) or < 0.95 (warn) |
| `trials_disclosed` | statistics | `n_trials` not declared (info only) |
| `holdout_consistency` | statistics | Sharpe positive in the first 70% and ≤ 0 in the last 30% (warn) |
| `period_consistency` | statistics | with 3 or more periods (years, quarters, months or equal segments): removing the best period leaves no profit (warn) |
| `benchmark` | statistics | info only: buy-and-hold (equal weight for a universe) on the same data and costs, next to the strategy |
| `walk_forward_oos` | statistics | `verify_grid` only: walk-forward out-of-sample Sharpe ≤ 0 (fail) or < 50% of the in-sample best (warn) |
| `parameter_plateau` | statistics | `verify_grid` only: the best combo's neighbours (one parameter one step away) keep < 50% of its Sharpe (warn): an isolated peak |

### Execution semantics

The verifier uses the same fee-aware research-bar engine as the rest of Monte-Neo:

- A signal on bar `t` fills at the open of bar `t + 1`.
- Commission and slippage are charged in bps per side on fill notional.
- Default costs: 5 + 5 bps per side.
- Default warm-up: `min(60, n_bars / 10)` bars.
- Positions are `+1` long, `0` flat, `-1` short, and shorts trade by default (`side_mode="long_short"`).
  Pass `model_from_costs(side_mode="long_flat")` to ignore short signals.
- Bars per year (for the annualized Sharpe) are counted over the elapsed time when the data
  spans 30 days or more, so weekends and nights are priced in: daily stocks give about 252.
  Shorter samples use the median bar step. `--periods-per-year` overrides it.

Sharpe statistics use per-bar returns after warm-up.

- **PSR** (Probabilistic Sharpe Ratio) is the probability that the true Sharpe is above 0.
- **Deflated Sharpe** is the probability that the true Sharpe is above the expected
  maximum Sharpe of `n_trials` zero-skill strategies. It uses the Bailey & López de Prado
  formulas with skew and kurtosis adjustments.

### Positions: signs or weights

`positions="auto"` (the default in the API, CLI `--positions`, MCP and the Action) reads the signal
as **weights** when every value is in `[-1, 1]` and at least one is fractional, and as **signs**
otherwise. Force either with `positions="sign"` or `positions="weight"`.

- **Signs:** any number is reduced to its sign; `+1` is a full long, `-1` a full short.
- **Weights:** the target fraction of equity, clipped to `[-1, 1]`. A weight that stays the same does
  not trade; a change trades only the difference (a change of side closes the position first).
  Costs are charged on the traded notional.

Sign strategies run on the same engine as before, so their numbers do not change. Weights run on
a target-weight engine that gives exactly the same equity as the sign engine on `+1 / 0 / -1`
(tested bit for bit). The resolved mode is in `metrics.positions` and in the certificate settings.

### Universes (several symbols)

Give the verifier a long table with a `symbol` column (`ticker`, `asset` and `instrument` work too)
and a `timestamp` column: one row per timestamp and symbol. The verifier sorts the rows by
timestamp, then symbol, and passes that table to `signal(df)`, which returns one weight per row.

```python
# universe.csv: timestamp, symbol, open, high, low, close
def signal(df):
    past = df.groupby("symbol")["close"].pct_change(20)
    rank = past.groupby(df["timestamp"]).rank(pct=True)   # rank within each timestamp
    return (rank > 0.7).astype(int) - (rank <= 0.3).astype(int)
```

- **Weights per timestamp** are capped at a gross exposure of 1: `+1` on ten symbols becomes ten
  longs of 10%. `metrics.gross_scaled_bars` counts the bars that were scaled.
- **Missing bars** are allowed: a symbol trades only on bars with a price. A position still open
  after a symbol's last price (a delisting) is closed at that price.
- **Look-ahead probes** cut and rewrite the future of every symbol at once, so a leak through
  another symbol (a join on the next day's market return) is caught like any other.
- **Survivorship:** if every symbol trades until the last bar, the `survivorship` check warns that
  the universe was probably picked from today's survivors.
- **Signals files** for a universe are tables with `timestamp`, `symbol` and a `signal` column,
  matched by key (missing rows are flat), or plain arrays in the sorted row order.
- The benchmark is an equal-weight portfolio of every symbol with a price.
- Row order in the input file does not matter: the certificate id is the same.

### Benchmark and breakdown

Every report has:

- `benchmark`: buy-and-hold on the same data, costs and warm-up (equal weight for a universe),
  and a `benchmark` info row with both returns and Sharpe ratios.
- `breakdown.periods`: return, buy-and-hold return, Sharpe and exposure per year, quarter or month
  (chosen from the span; four equal segments without timestamps).
- `breakdown.regimes`: results in rising and falling, calm and volatile markets. A bar's regime is
  set by the market's trailing return and volatility over the previous bars.
- `series`: up to 400 points of the strategy and buy-and-hold equity (scaled to 1), for charts.
  The MCP tools drop it from compact responses.

### HTML report

`--html report.html` writes a self-contained page next to the certificate: equity against
buy-and-hold with the drawdown, every check, what to fix, periods, regimes, the grid search and
the hashes needed to reproduce the run. It has no scripts and loads nothing from the network.
`--render verdict.json --html report.html` renders a certificate someone sent you. MCP tool:
`render_report`. The GitHub Action writes it too (output `html-report`).

### Timing significance

A long-biased strategy on rising data can pass every other check without any skill: it is
simply in the market while prices go up. The verifier shifts the strategy's own positions
circularly against the prices by 200 evenly spaced offsets. A shift keeps the exposure, the
number of trades and the holding periods, and destroys only the timing. The p-value is the
share of shifted copies that earn at least as much as the real one. The offsets are fixed,
so the result is reproducible. Selection over many variants is priced by the Deflated Sharpe,
not here.

### Why `n_trials` matters

When an agent tries 200 variants and reports the best one, the best Sharpe is
mostly luck. The verifier prices this in, but only if it knows the number of trials.
The trap suite (`tests/traps`) includes this case: the best of 200 random strategies
passes when `n_trials` is hidden and fails once `n_trials=200` is declared.

## Grid search inside the verifier: `verify_grid`

Agents tend to under-report `n_trials`. With `verify_grid`, the verifier runs the
parameter search itself, so the selection bias is measured instead of declared.

```python
from monte_neo.verify import verify_grid

# my_strategy.py:  def signal(df, fast=20, slow=80): ...
report = verify_grid("btc_1h.csv", {"fast": [10, 20, 40], "slow": [80, 120, 200]},
                     strategy="my_strategy.py", folds=4)
report["grid"]  # n_combos, best_params, top, walk_forward, plateau
```

What `verify_grid` does:

- Expands the grid, up to 512 combos.
- Runs every combo through the fee-aware engine and picks the best by per-bar Sharpe.
- Verifies that best combo with `n_trials = n_combos` and the measured Sharpe spread across trials.
- Runs an **anchored walk-forward**: parameters are re-chosen on past folds only and scored on
  the next fold. Its out-of-sample Sharpe becomes the `walk_forward_oos` check.
- Compares the best combo with its neighbours in the grid (`parameter_plateau`): a strategy
  that works only at one exact setting is fitted to noise.

CLI: `monte-neo verify --ohlcv data.csv --strategy my_strategy.py --grid '{"fast":[10,20],"slow":[80,120]}'`
(or `--grid grid.json`). MCP tool: `verify_grid`.

## Certificate (`strategy-verdict/1`)

```json
{
  "schema": "strategy-verdict/1",
  "verdict": "REJECT",
  "certificate_id": "17a9a29907e8d6ee",
  "reasons": ["lookahead_truncation: truncation probe: LEAK DETECTED"],
  "checks": [{"id": "...", "category": "...", "status": "fail", "summary": "...", "details": {}}],
  "metrics": {"total_return": -0.04, "deflated_sharpe": 0.11, "breakeven_cost_bps": 0.0},
  "next_actions": ["The signal at bar t changes when later bars are removed: ..."],
  "reproducibility": {"engine_version": "v0.18.0", "data_sha256": "...", "signals_sha256": "...",
                      "source_sha256": "...", "model": {}, "n_trials": 1,
                      "settings": {"min_trades": 30, "holdout_fraction": 0.3, "probe_checks": 24,
                                   "periods_per_year": null}},
  "generated_at": "2026-09-26T12:00:00+00:00",
  "disclaimer": "..."
}
```

`certificate_id` is derived from the reproducibility block and the verdict. The same
data, signals, code, model, `n_trials` and settings always give the same id. `settings`
records every threshold that can change the verdict (for example a lowered `min_trades`),
so a reader sees it and a re-check reuses it.

### Re-checking a certificate

A certificate is useful only if someone else can reproduce it. Re-check it with the
original data and the strategy file or signals file:

```bash
monte-neo verify --recheck verdict.json --ohlcv btc_1h.csv --strategy my_strategy.py
```

```python
from monte_neo.verify import recheck_certificate
recheck_certificate("verdict.json", "btc_1h.csv", strategy="my_strategy.py")["reproduced"]
```

How the re-check works:

1. It compares the data, signal and source hashes with the certificate.
2. It re-runs the verifier with the recorded execution model, `n_trials` and settings. For a
   grid certificate, it re-runs the recorded grid search.
3. It compares the verdict and the `certificate_id`. The engine version is part of the id, so
   a certificate from another release is re-checked with that release; the result names the
   `pip install monte-neo==X` command.

The result is `strategy-recheck/1`. `monte-neo verify --recheck` exits with code 4 when the
certificate is not reproduced. MCP tool: `recheck_certificate`.

### Signing a certificate

A re-check proves that the numbers are right. A signature proves who issued the certificate
and that nobody edited it afterwards. Monte-Neo signs certificates with Ed25519.
Signing needs the `sign` extra:

```bash
pip install "monte-neo[sign]"
monte-neo verify --keygen issuer          # writes issuer.key (keep secret) and issuer.pub
monte-neo verify --ohlcv btc_1h.csv --strategy my_strategy.py --sign issuer.key --out verdict.json
monte-neo verify --check-signature verdict.json --public-key issuer.pub
```

```python
from monte_neo.verify import check_signature, sign_certificate
signed = sign_certificate(report, "issuer.key")
check_signature(signed, public_key="ed25519:...")["key_matches"]
```

- The signature covers the canonical JSON of the certificate without its `signature` block:
  sorted keys, no whitespace, UTF-8. Changing any field, including the verdict or a metric,
  breaks it.
- The `signature` block stores the algorithm, the public key and its `key_id` (the first
  16 hex characters of the key's SHA-256).
- Without `--public-key`, a valid signature proves only integrity, because anyone can sign
  with a fresh key. Publish your `.pub` key (for example in your README) so that others can
  check who signed.
- The result is `strategy-signature-check/1`. MCP tool: `check_signature`.
- Anyone can also check a certificate in the browser on the [verification page](../verify.md);
  nothing is uploaded.
- The private key file is created with owner-only permissions. In CI, keep it in a secret.

## Bring your own signals: `export_signals`

```python
from monte_neo.backtest import export_signals
out = export_signals(o, h, l, c, positions, model=model, include_equity=True)
out["signal"]  # sha256, exposure, position_changes, has_short
```

## Security note

`strategy=` imports and runs the Python file with your permissions, as if you had run
it yourself. Only verify code you would run yourself.
