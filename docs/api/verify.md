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
monte-neo verify --ohlcv btc_1h.csv --strategy heavy_ml.py --jobs auto --timeout 120   # parallel probes, time limit
monte-neo verify --ohlcv btc_1h.csv --strategy their_code.py --isolate                 # no network, writes or secrets
monte-neo verify --ohlcv btc_1h.csv --strategy my_strategy.py --badge badge.json     # shields.io endpoint file
monte-neo verify --lint strategy.py other.py   # static lint only (pre-commit); exit 1 on a fail-level finding
monte-neo verify --precompile      # compile and cache the engines once (Docker images, CI caches)
```

- A strategy file may import modules from its own folder (a helper file, a package) and read a parameter file next to it. Under `--isolate`, reads stay allowed and writes stay blocked. Do not read price data files from strategy code: the `external_data` check fails on that.
- `--jobs N|auto`: run the look-ahead probes of a strategy file in N worker processes. Helps when
  one `signal()` call takes a noticeable time (ML models); a light strategy is faster with the default 1.
- `--timeout SECONDS`: a `signal()` call that runs longer ends the run with an error instead of hanging.
  The MCP server uses 300 s by default, the GitHub Action 600 s.
- `--isolate`: the strategy runs in worker processes without network, subprocesses, file writes
  outside the temp dir and secrets in the environment (see the security note).
- `--funding-bps-per-bar X` / `--borrow-bps-per-bar X`: funding on every open position and a borrow fee on short positions only, in bps of the position's value per bar (300 bps a year on hourly bars is about 0.034). Both are part of the certificate's cost model; a model without them keeps its certificate id. MCP and the Action take the same two settings.
- `--badge PATH`: also write a shields.io endpoint JSON with the verdict and certificate id.
- `--lint FILE...`: run only the static look-ahead lint on the files and exit (0, or 1 on a fail-level finding).
- `--precompile`: the first run in a new environment compiles the engines (about 4-5 s, then cached).

| Exit code | Meaning |
|-----------|---------|
| 0 | `PASS` or `PASS_WITH_WARNINGS` |
| 1 | `NEEDS_MORE_EVIDENCE` |
| 2 | `REJECT` |
| 3 | Usage or input error, including an invalid command-line option (not a verdict) |
| 4 | `--recheck`: the certificate was not reproduced |
| 5 | `--check-signature`: the signature is invalid, or the certificate was signed by a key other than `--public-key` |

## Verdicts

| Verdict | Rule |
|---------|------|
| `REJECT` | Any **integrity**, **lookahead** or **economics** check failed |
| `NEEDS_MORE_EVIDENCE` | Only **statistics** or **claim** checks failed |
| `PASS_WITH_WARNINGS` | No failures, at least one warning |
| `PASS` | Everything passed |

## Checks

| id | category | fails / warns when |
|----|----------|--------------------|
| `data_integrity` | integrity | NaN, non-positive prices, `high < low`, open or close outside high-low by more than 0.1% (smaller gaps are counted as vendor rounding), timestamps out of order (newest-first data) or duplicated, repeated (timestamp, symbol) rows in a universe (fail, stops the run early) |
| `data_quality` | integrity | well-formed but suspicious prices: one-bar spikes (a move over max(20 x robust scale, 5%) that the next bar takes back by 75%), frozen prices (runs of 5+ flat bars over 2% of the data), split-like jumps (open / previous close near 2, 3, 4, 5, 10, 20 or the inverse), gaps in time (beyond the usual nights and weekends), more than 5% of bars without volume (warn); fail when more than half of the profit comes from spikes in instruments the strategy held |
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
| `sharpe_confidence` | statistics | info only: 95% interval of the annualized Sharpe and of the total return from a circular block bootstrap (1000 resamples, fixed seed), and the share of resamples with a positive Sharpe |
| `track_record` | statistics | info only: the Minimum Track Record Length, how many bars the observed Sharpe needs to be positive at 95%, next to the bars the sample has |
| `spread_estimate` | economics | info only: a rough spread estimate from high and low (Corwin-Schultz) next to the slippage the backtest charged; says when the model looks optimistic |
| `capacity` | economics | info only, single instrument with a `volume` column: the capital at which 90% of the fills stay within 1%, 5% and 10% of the bar's traded value |
| `walk_forward_stability` | statistics | info only: the per-bar returns cut into 6 equal consecutive windows: how many made money, the worst and best window and the Sharpe of each |
| `claim_consistency` | claim | only with `--claim`: a claimed Sharpe, return, drawdown, trade count, win rate or profit factor is better than the verified one by more than a tolerance (fail) |
| `walk_forward_oos` | statistics | `verify_grid` only: walk-forward out-of-sample Sharpe ≤ 0 (fail) or < 50% of the in-sample best (warn) |
| `pbo` | statistics | `verify_grid` only: the probability of backtest overfitting (CSCV) is 0.5 or more: the best combination in training ranks below the median in testing (warn) |
| `reality_check` | statistics | `verify_grid` only: White's Reality Check and Hansen's SPA on the returns of every combination against cash; warns when the SPA p-value is 0.10 or more: luck cannot be excluded as the source of the best result |
| `parameter_plateau` | statistics | `verify_grid` only: the best combo's neighbours (one parameter one step away) keep < 50% of its Sharpe (warn): an isolated peak |

### How sure are we, and what was claimed

- **Confidence.** The certificate's `metrics` carry `sharpe_ci95`, `return_ci95` and `min_track_record_bars`. The
  bootstrap uses blocks of about the cube root of the sample, so autocorrelated returns keep their structure, and
  a fixed seed, so a certificate can be reproduced. These rows are context: the Deflated Sharpe decides.
- **PBO.** `verify_grid` splits the sample into 16 slices and, for each of the 12,870 ways to use half as
  training and half as testing, ranks the combination that won in training among all combinations in testing
  (Bailey, Borwein, Lopez de Prado and Zhu, 2015). PBO is the share of splits where the winner ranks below the
  median. It is a probability with real noise: about 0.4 on average for pure noise and near 0 for a strong
  edge that every combination shares.
- **Reality Check and SPA.** For a search, `reality_check` asks whether the best combination beats cash by more than the search explains. Both tests bootstrap the returns of all combinations (circular blocks, fixed seed, 1000 resamples). The Reality Check compares the largest mean with its null; SPA studentises and ignores clearly bad combinations, so many losing combinations do not hide a real edge. The SPA p-value decides the row; the Reality Check value is shown next to it. The benchmark is cash. Like every p-value from a bootstrap, it has sampling noise.
- **Costs and capacity.** The spread estimate is biased upward in volatile bars (a few bps at 0.3% bars, about
  15 bps at 1% bars): read it as an order of magnitude. Capacity takes `volume` in instrument units
  (traded value = volume x close) and does not model market impact.
- **Claims.** `--claim claim.json` (or `claim=` in Python and MCP, `claim:` in the Action) compares reported
  numbers with verified ones. All keys are optional: `sharpe` (annualized), `total_return` (fraction: `0.85` or `"85%"`),
  `max_drawdown`, `n_trades`, `win_rate` (`0.62` or `62`), `profit_factor`. A number that is better than the verified one by more
  than a tolerance (Sharpe 0.3 or 10%, return 2 points or 10%, drawdown 2 points or 10%, trades 2 or 5%, win rate 3
  points, profit factor 0.1 + 10%) fails `claim_consistency` and the verdict becomes `NEEDS_MORE_EVIDENCE`: the
  strategy may be fine, its report cannot be trusted. Win rate and profit factor need a trade journal (sign strategies on one
  instrument); for weights and universes they are reported as not verifiable. The claim is stored in the
  certificate's `reproducibility.settings`, so `--recheck` compares the same claim.

```bash
echo '{"sharpe": 2.1, "total_return": 0.85, "max_drawdown": 0.12, "n_trades": 300}' > claim.json
monte-neo verify --ohlcv btc_1h.csv --strategy my_strategy.py --claim claim.json
```

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

`--html report.html` writes a self-contained tear sheet next to the certificate:

- a one-sentence reason for the verdict, and a card per check family (integrity, look-ahead, economics, statistics);
- equity on a log scale against buy-and-hold, the drawdown, rolling Sharpe and a monthly-returns heat map;
- the distribution of returns, the timing test (200 shifted copies against the real return) and net return against trading costs;
- trade statistics (win rate, profit factor, average win and loss, holding time, streaks; sign strategies);
- what to fix, the evidence for a leak (the bars where the signal changed, the flagged source lines), every check, periods, regimes, the parameter heat map of a grid search, and the hashes needed to reproduce the run.

It has no scripts, loads nothing from the network, adapts to dark mode and prints to PDF from the browser.
See the [example reports](../gallery.md). `--render verdict.json --html report.html` renders a
certificate someone sent you. MCP tool: `render_report`. The GitHub Action writes it too (output `html-report`).

The data behind the charts is in the certificate's `charts` section (about 10 KB: monthly returns, a histogram, rolling
Sharpe, the cost curve, the shifted-copy returns and trade statistics). Like `series`, `benchmark` and `breakdown` it is
derived from the hashed inputs and is not part of `certificate_id`.

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

## Other frameworks and notebooks

Adapters for vectorbt, Freqtrade, Lean, Zipline and plain fills, the Jupyter display, the pandas accessor, the pre-commit hook and the
Docker image are described in [Frameworks and notebooks](../guides/frameworks.md).

## Bring your own signals: `export_signals`

```python
from monte_neo.backtest import export_signals
out = export_signals(o, h, l, c, positions, model=model, include_equity=True)
out["signal"]  # sha256, exposure, position_changes, has_short
```

## Without Numba

The engines are compiled with Numba, which is installed by default on CPython. Where Numba is not
available (PyPy, WebAssembly, a Python version without Numba wheels, `pip install --no-deps`), the
same source runs as plain Python: **certificates are identical bit for bit**, only the speed
differs. Nothing is downloaded at run time. Add Numba later with `pip install "monte-neo[fast]"`.

Measured on 4 cores (one instrument, a strategy that makes a profit, so the timing test runs):

| Bars | With Numba | Without: signs | Without: weights |
|-----:|-----------:|---------------:|-----------------:|
| 5 000 | 0.5 s | 2.4 s | 8 s |
| 20 000 | 0.2 s | 9 s | 34 s |
| 100 000 | 1 s | 46 s | 170 s |

A strategy that loses money skips the timing test and is about 4-10 times faster than the figures
above. Runs of 20 000 bars or more without Numba print a warning with the install hint.

## Security note

`strategy=` imports and runs the Python file with your permissions, as if you had run
it yourself. Only verify code you would run yourself.

`--isolate` (API `isolate=True`) guards against careless or buggy code: the strategy is loaded and
called only in worker processes, where an audit hook blocks network access, subprocesses, signals to
other processes, links (`os.symlink`, `os.link`) and file writes outside the temp dir (both ends of a rename count), and the environment keeps no secrets (only
`PATH`, `HOME`, locale and temp variables). It is **not** a security boundary against a determined
attacker: native code or ctypes can get around Python audit hooks.

To verify code you do not trust (a marketplace, a prop firm, a competition), run the verifier in a
throw-away container without network and with the data mounted read-only:

The repository ships the image: [`docker/verify/Dockerfile`](https://github.com/NeoZorK/Monte-Neo/blob/main/docker/verify/Dockerfile)
(`python:3.12-slim`, the verifier compiled at build time, runs as `nobody`).

```bash
docker build -t monte-neo-verify docker/verify    # add --build-arg VERSION=X.Y.Z to pin a release
docker run --rm --network none --read-only --tmpfs /tmp \
  --memory 4g --cpus 2 --pids-limit 256 \
  -v "$PWD/data:/data:ro" -v "$PWD/submission:/code:ro" -v "$PWD/out:/out" \
  monte-neo-verify monte-neo verify --ohlcv /data/prices.csv --strategy /code/strategy.py \
    --isolate --timeout 300 --out /out/verdict.json
```

The container has no network, a read-only file system (except `/tmp` and `/out`) and limits on
memory, CPU and processes; `--isolate` and `--timeout` still apply inside it. Every run starts from
the image: a file a strategy writes to `/tmp` is gone after the run. Tested with a strategy that tries
to open a connection and write into `/code`: both are blocked, and the check finishes in about 2 s.

### Inputs are limited

Every input has a size limit with a clear error: price tables 2 GB (raise it with `MONTE_NEO_MAX_INPUT_MB`),
certificates 64 MB, strategy files 5 MB. Certificate JSON is read strictly (no duplicate keys, no `NaN`,
nesting up to 100 levels), and the browser verification page applies the same rules. The MCP tool
`render_report` writes only `.html` / `.htm` files. See [SECURITY.md](https://github.com/NeoZorK/Monte-Neo/blob/main/SECURITY.md)
for the threat model and how to report a vulnerability.
