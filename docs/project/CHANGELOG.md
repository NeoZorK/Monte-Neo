# Changelog

All notable releases are documented here.
Version source of truth: `src/monte_neo/_version.py`.

## [v0.52.0] — 2026-10-05

### Added
- **`bench run --clean-env`** starts the agents without `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` and
  `ANTHROPIC_MODEL`, so they use their own login; the Claude Code message "issue with the selected model" now gets a one-line fix.
  A troubleshooting section in [guides/agents.md](../guides/agents.md) explains the variables.
- **Local agents:** `qwen-code` is a built-in `bench run` agent; `bench run --base-url` points an agent at a model on your
  machine (Ollama, LM Studio) and checks the server before any task; known failure messages get a one-line fix, and an agent
  that failed is not run on its remaining tasks. `integrations/qwen/` (rules and MCP entry). See [guides/local-agents.md](../guides/local-agents.md).
- **`monte-neo discover`** and MCP tool `discover_indicator`: a search over causal formulas with a causality gate, canary
  leaks, effective-trial counting, a search null on shuffled markets, Reality Check / SPA / PBO, a lockbox opened once and a
  certificate; optional evolution (`--evolve`) and `--recheck` of a recorded search. See [guides/discover.md](../guides/discover.md)
  and the generated [calibration](../guides/discover-calibration.md).
- **Repaint checks** `repaint_history` and `repaint_live` (`--repaint off|auto|strict`, `--signal-timing close|open`): a
  signal must not change after it was shown, and the forming bar is tested at 0, 25, 50 and 75 % of its path. Lint rules
  `repaint_zigzag`, `unconfirmed_pivot`, `htf_without_shift`, `lookahead_on`; `suggest_fix` shifts a higher-timeframe
  aggregate. See [guides/repaint.md](../guides/repaint.md).
- **Trial ledger** (`verify --ledger`, MCP `ledger`): counts the variants tried on the same data; `n_trials` is the larger
  of the count and the declared value.
- **`verify --suggest-fix FILE`** and MCP tool `suggest_fix`: causal rewrites with a diff.
- **Project tools** ([guide](../guides/workflow-tools.md)): `history` (certificate history, diff, regression exit code,
  pull-request table), `register` (pre-registration, `--registration`), `oracle` (Thresholdout hold-out oracle),
  `portfolio` (effective number of strategies, SPA over the list), `doctor` (known problems of data exports). MCP tools
  `compare_certificates`, `register_hypothesis`, `holdout_query`, `verify_portfolio`, `diagnose_data`.
- **`serial_correlation`** (info): the Sharpe corrected for serial correlation (Lo, 2002).
- **Data checks:** 20 or more identical bars in a row, and a market that never closes skipping bars (1 % of the steps); quote
  checks for repeated rows and a stalled feed.
- **Hypothesis zoo** (`tests/zoo`): about 170 mechanisms in six disguises (1026 cases), repaint (A14), data defects (21 x 3
  frequencies), economics (A5), statistics (A6), universes (A10), machine learning (A11), quotes (A12), planted claims and
  metamorphic relations, an independent oracle, a ratchet of known gaps (now empty), a generated
  [honesty scorecard](../guides/honesty-scorecard.md) (`scripts/zoo_scorecard.py`). The lite level runs in CI, the full one nightly.
- Agent rules (`integrations/`) mention the ledger, `suggest_fix`, repainting, the hold-out oracle and `discover_indicator`.

### Changed
- **A stop that a bar gaps through leaves at the open**, not at the stop level (long: the lower of stop and open; short: the
  higher). Before, a gap of 12 % through a 5 % stop was booked as a 5 % loss. Take-profit keeps its level. Results of
  strategies with `--sl-pct` / `--trail-pct` can get worse; certificates of such strategies change.
- Lint: an assigned-and-never-read future value, and a private helper nothing calls, are warnings instead of failures;
  `uniform_filter1d` with a trailing `origin` is causal.
- Ledger and registry stamps have microsecond resolution.

### Known limits
- Universes skip `data_independence` and the repaint probes. The Freqtrade and Lean adapters are tested on fake data only.
  A model fitted when the module loads that still reacts to its input is not caught by the probes. Hansen's SPA is a little
  liberal in small samples (about 7 % at a nominal 5 %).

## [v0.51.0] — 2026-10-04

### Added
- **`data_independence` check.** The strategy is run on a random walk of the same volatility, then on that walk with every
  date shifted. A strategy whose positions do not change on either one ignores its input: a cache between calls, an
  array computed in advance, a table keyed by date. It is a warning, and a failure (REJECT) when the strategy also
  earns an annualized Sharpe of 6 or more. Calendar rules (hour of day, weekday) are recognised and pass.
- **`implausible_performance` check**: a warning when the annualized Sharpe after costs is 6 or more.
- Lint rules `cached_signal` (`lru_cache`, `cache`, `cached_property`), `import_time_fit` (`.fit()` when the module loads)
  and `global_state` (`global`), all warnings.

### Fixed
- **A leaking strategy that kept its answer between calls passed as PASS.** A strategy that computed the leaky answer once
  on the full table and returned prefixes (or held an array computed in advance) beat the truncation and perturbation
  probes, and nothing else looked at its Sharpe of 57. Found by measuring the plan of stages 8-10; the three variants are
  now rejected (`tests/unit/test_verify_stateful.py`). Model fits on the whole file that still react to their input
  remain a limit of any verifier that runs your code: see "What the probes cannot prove" in the API guide.
- Cost: one probe adds two extra runs of `signal()` (0.4 s on 50,000 bars).

## [v0.50.0] — 2026-10-01

**Latency audit (experimental).** The new `--quotes` checks are context: they warn, they do not fail the verdict, and they were
calibrated on synthetic data and checked on 1.18 million real quotes with an assumed latency. Read the
[guide](../guides/arrival-time.md) before relying on a number.


### Added
- **Quotes with arrival time** (`monte_neo.verify.quotes`): load top-of-book quotes with their latency, check them
  (`quote_quality`: crossed and non-positive quotes, negative latency, out-of-order arrivals, latency percentiles per
  venue, share of stale quotes, rows that did not parse) and build mid-price bars on the exchange clock or the arrival clock.
- **Arrival look-ahead** (`monte_neo.verify.arrival.arrival_lookahead`): the strategy sees bars binned by stamp + latency and
  trades against the market bars; `warn` when its profit exists only with zero latency.
- **`latency_scan`**: profit when data arrives later, and the delay at which it vanishes.
- **`latency_monte_carlo`**: the same strategy over 200 seeded redraws of the observed latency; distribution of the
  return and the probability of a loss.
- **`verify_quotes`**, **`monte-neo verify --quotes`** (`--bar-ms`, `--latency-samples`, `--demo-quotes`) and the MCP tool
  `verify_quotes`: one `strategy-verdict/1` certificate from the four checks plus `net_profitability` on the exchange
  clock; the HTML report gets a "Time and latency" section with a return-against-delay chart.
- Traps and honest controls for the arrival checks (`tests/traps/test_quote_traps.py`): three traps draw their warning,
  seven honest strategies (four seeds, three latencies) pass with no warning.
- The arrival checks are `warn` at most; a strategy that loses money on the exchange clock is rejected, as in `verify_strategy`.
- **Quote recorder** (`python -m monte_neo.data.quote_recorder`): records Binance USD-M futures `bookTicker` quotes with
  their latency (receive time corrected by the clock offset to the exchange, minus the event time) into the table
  `verify --quotes` reads. It reports how well the offset is known and warns when the latencies cannot be trusted
  (proxy, VPN, slow network); a dropped connection keeps what was recorded.
- `verify_quotes` says plainly when a recording has too few bars for the warm-up.
- **`--symbol`** picks one instrument from a table of several (an unclear table is an error that lists the symbols);
  **`--order-latency-ms`** delays every fill by a constant, so an edge that lives in instant execution is rejected.
- **`--recheck` for quote certificates**: `monte-neo verify --recheck CERT --quotes Q --strategy S`, `recheck_quotes()` and the
  MCP tool `recheck_certificate(quotes_path=...)` reproduce the certificate id from the quotes, the code and the recorded
  settings; changed quotes or code are named in `inputs_match`.
- **`--latency-model`** (`constant:MS` or `lognormal:MEDIAN,P95`) assumes the data latency instead of reading it (the table needs no
  latency column); the certificate records it and says the latency is assumed, not measured.
- **`--symbol` + `--feeds`**: a strategy may read other instruments (`<alias>_close`...), each feed with its own latency;
  `synthetic_feeds` is the latency-arbitrage test pair. A leader that arrives after the follower moved turns the edge into a loss.
- **Look-ahead probes on the arrival bars** (`--no-probes` skips): a strategy that reads the next bar is rejected, which the
  clock check alone cannot see.
- **`spread_cost`** warns when the modeled slippage is below the half-spread a taker pays; every certificate carries
  `assumptions` (taker fills at the mid, no queue position, no partial fills, order delay, latency source), shown in the report.
- `latency_tolerance` calls the profit vanished only when two scanned delays in a row earn nothing: one noisy point of a thin
  honest edge no longer warns.
- **Checked on real quotes** (`scripts/validate_on_real_quotes.py`, 1.18 million real quotes of BTC, ETH and SOL futures, assumed
  latency): 36 honest runs, no false accusation (33 lose money after costs, 3 pass); the foresight control is rejected 3 of 3; an edge
  planted on the real SOL path (a follower that repeats it 2 s later) is caught at the matching delay. Almost no honest
  strategy earns on real prices, so the false-warning rate among earning strategies is still unmeasured.
- A guide ([Latency audit](../guides/arrival-time.md)), a second demo GIF (`docs/assets/demo-arrival.gif`, rendered from live
  runs by `scripts/make_arrival_gif.py`) and the README section that explains what the feature catches and what sets it apart
  (an audit of a finished strategy, not an environment).
- Measured speed on 1 million quotes: load 0.6 s, `verify_quotes` with 200 latency draws on 100 ms bars 7 s (see docs/api/verify.md).
- `quote_quality` warns about **bursty latency** (p99 more than 20 times the median, from 100 quotes): a congested path
  (VPN, Wi-Fi) holds messages back and releases them in bursts, and the arrival checks would then measure the network.
  Found on a real two-minute recording: latency climbed from 0.5 s to 12 s and drained in one burst.
- The recorder measures the clock offset over one keep-alive connection (a new connection per sample inflated the
  round trip about three times), and `verify --quotes` takes costs and warm-up into `verify_quotes`.

### Security
- `virtualenv` 20.36.1 -> 21.14.2 in `uv.lock` (four Dependabot advisories; a development tool pulled in by `pre-commit`, not a runtime dependency).
- The release SBOM is built from `scripts/requirements/runtime.txt`, a hash-locked file made from `uv.lock` (a test keeps it in
  step), and the package itself installed with `--no-deps`; the verifier image installs the release with `--require-hashes`
  (hashes read from PyPI by `scripts/build_docker_image.sh`). This closes the two remaining Pinned-Dependencies findings.

## [v0.49.0] — 2026-09-30

### Added
- **`monte-neo init-ci`**: writes a GitHub Actions workflow that verifies your strategy on every pull request. It finds the
  strategy file and the price table in the project (or takes `--strategy` / `--ohlcv`), pins the checkout to a commit and the
  action to the installed release, posts the verdict as a pull-request comment and uploads the certificate. Options:
  `--n-trials`, `--fail-on`, `--isolate`, `--sign`, `--out`, `--print`, `--force`. It never overwrites a file without `--force`.

## [v0.48.0] — 2026-09-30

### Added
- **Adapters for more real frameworks**: `from_backtrader` (the `Transactions` analyzer), `from_backtesting_py`
  (`stats["_trades"]`), `from_bt` (security weights) and `from_nautilus` (the engine or its fills report).
  A CI job now runs a moving-average strategy in each installed framework (Backtrader, backtesting.py, bt,
  vectorbt, Nautilus Trader, Zipline) and compares what the adapter reads with the position the framework itself
  held on every bar. The framework versions are hash-locked (`scripts/requirements/frameworks.txt`).
- `from_fills(..., fill_at="open" | "close")`: say where in its bar a fill happens.

### Fixed
- **Close fills were read one bar too early.** `from_fills` treated every fill as an open fill, so a framework that
  fills at the close of the decision bar (Nautilus on bar data) gave the strategy one bar of foresight: its results
  looked better than they were. `from_nautilus` reads such fills at their own bar, and `fill_at` covers the rest.
- `from_zipline` read a daily transaction, stamped with the session close time, one bar late; it now uses the session date.
- An empty list of fills (a strategy that never traded) raised a confusing error; it now means flat all the way.

## [v0.47.0] — 2026-09-30

### Added
- **`monte-neo verify --demo`**: a first run with no files. It verifies a strategy that peeks at tomorrow's close and a
  no-peeking moving-average crossover on synthetic prices, and says for each whether the look-ahead checks are clean.
- **Plain-language summary** under the check table of every text run: what the verdict means, the first reason and how
  many more there are. The certificate and its id are unchanged.

## [v0.46.0] — 2026-09-30

### Added
- **Capacity for universes.** The capacity row now works for multi-symbol runs: each order (capital x weight change) is set
  against the traded value of that symbol at the fill bar, and the capital at which 90% of the fills stay within 1%, 5% and 10%
  of it is reported. The row names the tightest symbols, and the HTML report gets a "Capacity by symbol" table. Fills at bars
  without volume are counted, not used. Single-instrument capacity and all certificate ids are unchanged.

## [v0.45.0] — 2026-09-30

### Added
- **Per-symbol costs for universes** (`--costs-file`, MCP `symbol_costs`, Action `costs-file`, Python `symbol_costs=`): a JSON
  mapping gives each symbol its own commission and slippage in bps, with a `default` row; a symbol takes its own values, then
  `default`, then the uniform costs. A name that is not in the data is an error. The resolved table is written into the
  certificate's cost model (one row per symbol), so a recheck needs no other input; a run without per-symbol costs keeps its
  certificate id. The target-weight engine charges each instrument its own costs; a table of equal rows equals the uniform model
  bit for bit, and an independent reference covers different costs. The cost checks and the report use the average of the rows.
  The engines that would ignore per-symbol costs (single instrument, batch, shared-cash) refuse them.

## [v0.44.0] — 2026-09-30

### Added
- **Stops inside the bar for target weights.** `sl_pct`, `tp_pct` and `trail_pct` now work in the target-weight engine
  (fractional weights and universes), using each instrument's high and low. With weights in {-1, 0, 1} on one
  instrument the result equals the discrete engine bit for bit, stops included (tested on hundreds of random
  configurations with costs, funding, borrow fees, leverage and both fill policies), and an independent reference
  covers fractional weights over several instruments. Models without stops give bit-identical results to before, and
  the pure-Python fallback gives the same numbers.
- **Stops in the verifier:** `--sl-pct`, `--tp-pct`, `--trail-pct` in the CLI, `sl_pct` / `tp_pct` / `trail_pct` in the MCP
  tools and `model_from_costs`, and the same inputs in the GitHub Action. They are part of the certificate's cost model and
  appear on the report's cost line. The buy-and-hold benchmark never uses them.

### Changed
- `run_weight_backtest` takes optional `high` and `low`; a model with stops and no high and low is an error (it used to
  refuse stops for weights altogether).

## [v0.43.2] — 2026-09-30

### Security
Findings from a full security pass (Bandit over all of `src`, `pip-audit` over the whole lock file including dev
dependencies, secret scanning of the tree and history, review of every workflow). None touched the verifier's own code.

- Research modules: the calibration cache no longer reads or writes pickle files (loading a pickle runs code); its
  directory is created private (700); the cache key hash is marked as not security-relevant.
- Dynamic indicators: expressions are checked (no private names or attributes) and run with a whitelist of built-ins
  instead of the full set.
- The generated `compile.sh` is executable by its owner only.
- `pypi-smoke.yml` passes the resolved version through the environment instead of splicing it into the script.
- Bandit in CI now covers all of `src`.

## [v0.43.1] — 2026-09-30

Quality release after a full check of the product as a customer (clean install from PyPI on Python 3.11, 3.12 and 3.13,
every command, the MCP server on SDK 1.x and 2.x, the Action script, the Docker image, real vectorbt and Backtrader runs,
an independent re-implementation of both engines and of the Sharpe statistics, 70+ edge inputs).

### Fixed
- **A strategy split over several files now works.** A helper module, a package or a parameter file next to the strategy
  file failed with `No module named ...` in every mode. The strategy's folder is now on the import path (at the end, so it
  can never shadow numpy or the standard library).
- `monte-neo --help` (and `-h`, `help`) print the commands instead of failing without the research extra; an unknown
  command says so.
- A command-line usage error (`--n-trials abc`) exits with **3**, not 2: 2 means REJECT and must not appear for a typo.
- `from monte_neo.verify import *` exposes every public name (`show`, `from_vectorbt`, ...); a test keeps `__all__` complete.
- A headerless signals CSV keeps its first value (it used to lose it: "signal length 2999 != bar count 3000").
- CSV files separated by `;`, tab or `|` are read.
- The HTML report no longer prints `None` for a signals-only run, names the right recheck option, and mentions funding and
  borrow fees when the model has them. The example gallery is regenerated with the current engine.
- The static lint no longer warns on `model.fit(X[train], y[train])` (a fit on a chosen slice, as in walk-forward code);
  a fit on a whole array still warns.
- `Certificate` prints one summary line instead of a 50 KB dict; a grid whose values are not lists says so.
- The pre-commit guide shows how to limit the hook to strategy files.

## [v0.43.0] — 2026-09-30

### Added
- **Short-borrow and funding fees.** `--funding-bps-per-bar` (every open position) and the new `--borrow-bps-per-bar`
  (short positions only), in the CLI, MCP tools (`funding_bps_per_bar`, `borrow_bps_per_bar`), the GitHub Action and
  `model_from_costs`. Both engines (sign and target-weight) charge them; the batch and shared-cash engines refuse a
  model that sets a borrow fee instead of ignoring it. The fee is part of the certificate's cost model only when set,
  so existing certificates keep their ids and recheck.
- **Reality Check and SPA** for `verify_grid`: the new `reality_check` row (White 2000, Hansen 2005) tests whether the best
  combination beats cash by more than the whole search explains; it warns at an SPA p-value of 0.10 or more.
- **Rolling stability** (`walk_forward_stability`, context): the returns cut into 6 equal windows, how many made money and
  the worst and best window. `metrics.windows_positive`.

## [v0.42.0] — 2026-09-30

### Added
- **Technical note** on the verification method (`docs/paper/methodology.md`, also on the docs site): probes, costs,
  selection, certificates and the Trap Suite evaluation.
- **Trap of the week:** twelve post drafts with measured verdicts (`docs/marketing/trap-of-the-week.md`).
- README: "How it differs from other tools" and a link to the note; issue form for **false accusations**.
- conda-forge recipe draft (`packaging/conda-forge/meta.yaml`), list and catalogue entries in the launch kit.

### Fixed
- The Docker image on GHCR is built by the `docker` job of `publish.yml` (after the PyPI smoke test), through
  `scripts/build_docker_image.sh`, which waits for the package index. `docker.yml` is a manual rebuild. In v0.41.0 the
  separate `workflow_run` build never started and the first manual run hit the index delay.

## [v0.41.0] — 2026-09-29

### Added
- **Framework adapters.** `from_vectorbt`, `from_freqtrade`, `from_lean`, `from_zipline` and `from_fills` turn a
  backtest run elsewhere into positions on the price table; `.verify()` runs the verifier on them. Backtrader and
  Nautilus use `from_fills` (recipe in the guide). See `docs/guides/frameworks.md`.
- **Jupyter display.** `verify_strategy` and `verify_grid` return a `Certificate` (a `dict` subclass) that draws the HTML
  report in a notebook cell inside a sandboxed frame; `show(cert)` does the same for a loaded certificate.
- **pandas accessor** `df.monte_neo.verify(...)` (`import monte_neo.verify.accessor`).
- **Badge.** `--badge PATH` writes a shields.io endpoint file with the verdict and certificate id.
- **pre-commit hook** `monte-neo-lint` and `monte-neo verify --lint FILE...` (static lint only, exit 1 on a fail-level finding).
- **Docker image on GHCR.** `.github/workflows/docker.yml` builds and pushes `ghcr.io/neozork/monte-neo-verify` after each
  successful Publish run (plain docker CLI, no third-party action).

## [v0.40.0] — 2026-09-29

### Added
- **Trap Suite: 80 traps and 35 honest controls** (was 55 and 25). New traps cover machine-learning pipelines
  (shuffled and K-fold splits, whole-sample PCA, k-means, k-NN, feature selection, hyper-parameter tuning,
  scaling, winsorizing, volatility targeting, start-date picking), calendar joins (`transform("last")`,
  `merge_asof`, `resample(closed="right")`, whole-day VWAP), universes (future volatility rank, whole-sample
  winners, today's membership applied to the past, total-sample normalisation) and honest code on damaged data
  (unadjusted split, frozen feed, outages). Each trap has an honest twin that must never be flagged.
- **Two lint rules:** `shuffled_split` (`train_test_split` without `shuffle=False`; fail when `shuffle=True`) and
  `kfold_split` (K-fold and shuffle splitters on a time series; fail for `shuffle=True` and `ShuffleSplit`).
  The lint now has 23 rules.
- Test datasets `frozen_feed`, `unadjusted_split` and `feed_outages`.

## [v0.39.0] — 2026-09-29

### Added
- **Claim check (`--claim`).** Report the numbers you are about to claim (`sharpe`, `total_return`, `max_drawdown`,
  `n_trades`, `win_rate`, `profit_factor`) and the verifier compares them with the verified ones. A claim better
  than the verified result by more than a tolerance fails the new `claim_consistency` check (category `claim`,
  verdict `NEEDS_MORE_EVIDENCE`). CLI `--claim`, MCP `claim` on `verify_strategy` and `verify_grid`, Action input
  `claim`, Python `claim=`; the claim is recorded in the certificate so `--recheck` compares the same one.
- **Confidence.** `sharpe_confidence`: 95% interval of the Sharpe and of the total return (circular block
  bootstrap, fixed seed) and the share of resamples with a positive Sharpe; `track_record`: the Minimum Track
  Record Length. Also in `metrics` (`sharpe_ci95`, `return_ci95`, `min_track_record_bars`). Context only.
- **PBO for parameter searches.** `verify_grid` computes the probability of backtest overfitting by CSCV over
  12,870 train/test splits; the new `pbo` check warns at 0.5 or more. The report shows the rank distribution.
- **Costs and capacity.** `spread_estimate`: a rough Corwin-Schultz spread from high and low next to the modeled
  slippage (flags an optimistic model); `capacity`: the capital at which 90% of fills stay within 1%, 5% and 10% of
  the bar's traded value (single instrument with a `volume` column). Context only; both show in the report cards
  and the cost-sensitivity chart.
- Trap Suite: an overclaim test; the false-positive corpus of honest strategies still raises no alarms.

### Notes
- Existing certificates and `certificate_id` values are unchanged when no `--claim` is given: the new rows are
  `info` (never change the verdict) except `pbo`, which only appears for parameter searches.

## [v0.38.0] — 2026-09-29

### Added
- **The HTML report is now a tear sheet.** A one-sentence reason for the verdict, a card per check family, equity on a
  log scale with the drawdown, rolling Sharpe, a monthly-returns heat map, the distribution of returns, the timing
  test (200 shifted copies against the real return), net return against trading costs, trade statistics (win rate,
  profit factor, average win and loss, holding time, streaks), the evidence for a leak (the bars where the signal
  changed and the flagged source lines with the code), a parameter heat map for grid searches, and a print
  stylesheet (PDF from the browser). Still one file: no scripts, no network.
- **`charts` section in the certificate** (about 10 KB) with the data behind the charts. It is derived from the
  hashed inputs and is not part of `certificate_id`, so existing certificates and IDs are unchanged.
  Grid certificates also record `combo_sharpes`.
- **Gallery of example reports** (`docs/gallery.md`, `scripts/make_report_gallery.py`): a leak, no edge, an honest
  strategy, a parameter search, a universe and bad ticks.

### Fixed
- A malformed or hostile certificate (numbers where lists are expected, text in chart data) could crash the HTML
  renderer; every chart now validates its input.

## [v0.37.0] — 2026-09-29

### Security
Result of the security audit (policy and threat model: `SECURITY.md`).
- **`--isolate` could be bypassed** by renaming a temp file over any file, or by creating a symbolic or hard link in
  the temp dir and writing through it. Both ends of a rename are checked, links are blocked, paths are resolved
  with `realpath`. Reproduced by four new tests. `--isolate` remains a guard, not a security boundary.
- **A certificate could make the verifier open a file:** the public key inside a certificate was treated as a file
  name. It is now only text; the key you pass to check against may still be a file.
- **The verification page showed a green tick for a forger's own key.** A certificate signed with any key looked
  "valid (integrity only)". Now only a match with the expected issuer key is green; otherwise it says the signer is
  not verified. The page also rejects ambiguous JSON, limits the loaded file (8 MB, 15 s) and sends no referrer.
- Strict certificate JSON (no duplicate keys, `NaN`, depth over 100), size limits for every input
  (`MONTE_NEO_MAX_INPUT_MB` for tables), MCP `render_report` writes only `.html` / `.htm`, the HTML report has a
  Content-Security-Policy.
- Dependency `click` upgraded in the lock file (advisory PYSEC-2026-2132, transitive via `mcp`).
- Supply chain: all GitHub Actions pinned to commit SHAs, read-only default permissions in every workflow, new
  `security.yml` (Bandit, pip-audit) and `scorecard.yml` (OpenSSF Scorecard), CycloneDX SBOM attached to releases.

### Added
- **The verifier runs without Numba.** Where Numba cannot be installed (PyPy, WebAssembly, a Python without
  Numba wheels, `--no-deps`), the same engine source runs as plain Python: certificates are identical bit for
  bit (tested end to end in a process without Numba), only the speed differs (about 50-200x slower for a
  profitable strategy, see `docs/api/verify.md`). A warning with the install hint appears from 20 000 bars.
  Numba is now a CPython-only dependency and has an extra: `pip install "monte-neo[fast]"`. Nothing is
  downloaded at run time.

## [v0.36.1] — 2026-09-29

### Fixed
- **Slow checks of high-turnover strategies.** Every backtest built a Python journal of all trades that the verifier
  never read: a strategy with 100 000 trades on 200 000 bars took 9.8 s, now 0.5 s (same numbers bit for bit; the
  verifier uses a journal-free path of the same engine).
- **Crash in read-only environments.** With no writable directory for Numba's cache (a read-only container, a user
  without a home directory) importing the engines failed with "cannot cache function". They now compile in memory.

### Changed
- Release cadence: the limit of 2 feature releases a day is removed; releases can be published at any time
  (each still needs the owner's approval).

### Added
- **Docker image for untrusted code:** `docker/verify/Dockerfile` (engines compiled at build time, runs as
  `nobody`), tested with the documented no-network, read-only run.

## [v0.36.0] — 2026-09-29

### Added
- **Data quality check (`data_quality`).** Data can be well formed and still wrong. The new check looks for
  one-bar price spikes that the next bar undoes (bad ticks), runs of frozen prices, split-like jumps
  (unadjusted splits), gaps in time beyond the usual nights and weekends, and bars without volume. Findings
  warn; the check fails when more than half of the profit comes from spikes in instruments the strategy held.
  Works on one instrument and on universes (reads a `volume` column when present).
- **Trap Suite: bad data.** New `bad_ticks` dataset and `spike_fade` trap: honest code whose profit is bad
  ticks must be rejected (55 traps, 25 honest controls).
- **Strategy workers.** `jobs` (CLI `--jobs`, MCP, Action) runs the look-ahead probes of a strategy file in
  parallel worker processes; `timeout` (CLI `--timeout`, default 300 s in MCP, 600 s in the Action) ends a
  `signal()` call that hangs with a clear error; `isolate` (CLI `--isolate`) blocks network, subprocesses
  and file writes outside the temp dir and removes secrets from the environment of the workers.
- **`monte-neo verify --precompile`** compiles and caches the engines (about 4 s once): the first check in a new
  environment takes 1.6 s instead of 6 s. For Docker images and CI caches.
- **Docs: verifying untrusted code.** What `--isolate` does and does not protect against, and a Docker recipe
  (no network, read-only file system, resource limits) for marketplaces and prop firms.

### Changed
- **Lighter install: 488 MB -> 327 MB.** The base install is the verifier, the CLI (`verify`, `bench`) and the
  MCP server. Research packages moved to extras: `parquet` (pyarrow, for `.parquet` tables) and `research`
  (the interactive `monte-neo` menu). Both print the extra to install when it is missing; the GitHub Action
  installs `parquet` by itself for `.parquet` inputs.
- Tests that need MLX / Metal are skipped on machines without MLX (Linux) instead of failing; they still
  run on the macOS CI job.

## [v0.35.1] — 2026-09-29

### Fixed
- **Broken bars passed the data check.** A bar whose open or close lay outside its high-low range (a close 20%
  above the high, an open at half the low) was "clean". `data_integrity` now fails such bars when the gap is over
  0.1% of the price; smaller gaps are vendor rounding and are counted in the details.
- **MCP errors lost their reason.** The SDK answered any exception with "Error executing tool verify_strategy",
  so an agent could not tell a wrong path from a broken strategy. Tools now return `{"error": "FileNotFoundError:
  ...", "tool": ...}`.
- **Unhelpful input errors:** `signal()` returning `None` or one number now says so (it said "signal length 1 !=
  bar count"), text positions say positions must be numbers, and universe rows without a symbol are reported
  instead of failing inside a sort.
- **Slow start.** `monte-neo` loaded the interactive research menu (and pandas) before every command:
  `--version` now takes about 40 ms instead of 900 ms and `verify --help` about 140 ms. New entry point
  `monte_neo.cli.entry`; `monte_neo.cli` loads its attributes lazily.
- Universe perturbation probe: the future of every symbol is mirrored from a per-symbol index built once
  (same result, about 20% faster on 300 symbols x 1500 bars).

## [v0.35.0] — 2026-09-29

### Added
- **Fractional positions (weights).** A signal can now be a fraction of equity in `[-1, 1]` (`0.5` = long
  half the equity). `positions="auto"` (API, CLI `--positions`, MCP, Action) reads weights when every value is
  in `[-1, 1]` and one is fractional, else signs; `sign` and `weight` force the reading. Weights run on a new
  target-weight engine (`monte_neo.backtest.weight_engine`): only changes trade, costs are charged on the traded
  notional, a change of side closes first. On `+1 / 0 / -1` it gives the same equity as the sign engine bit for
  bit (400 random scenarios, and in CI). Sign strategies keep their exact numbers and certificate ids.
- **Universes.** A table with a `symbol` column (`ticker` / `asset` / `instrument`) and a `timestamp` column
  is verified as a portfolio: `signal(df)` returns a weight per (timestamp, symbol) row, gross exposure is capped
  at 1 per timestamp, symbols may list late or stop trading (open positions close at the last price). The
  truncation and perturbation probes cut and rewrite every symbol's future at once, so leaks through another
  symbol are caught. New `survivorship` check warns when no symbol stops trading (a survivors-only universe).
  Signals tables are matched by (timestamp, symbol). Row order in the input does not change the certificate.
  Grid search, re-check, the MCP tools and the Action all work on universes.
- **Trap Suite:** `xs_next_return_rank`, `xs_market_future_join`, `xs_symbol_history_rank` (54 traps) and the
  honest controls `xs_momentum_rank`, `xs_equal_weight` (25), plus a survivors-only universe test.
- **Buy-and-hold benchmark** on the same data and costs (equal weight for a universe): a `benchmark` info row,
  `metrics.benchmark_total_return` / `benchmark_sharpe_annualized` and a `benchmark` section.
- **Breakdown:** results per year, quarter or month (or four segments) and per market regime (rising / falling,
  calm / volatile, set by the trailing market return and volatility). New `period_consistency` check warns when
  removing the best period leaves no profit.
- **HTML report:** `--html report.html` (and `--render CERT --html report.html` for an existing certificate)
  writes one self-contained page: equity against buy-and-hold with drawdown, checks, what to fix, periods,
  regimes, grid, reproduction hashes, signature status and a link to the verification page. No scripts, nothing
  loaded from the network, every certificate string escaped. MCP tool `render_report`; the Action writes it,
  uploads it with the certificate and exposes it as the `html-report` output.
- The certificate `series` (up to 400 equity points) feeds the charts; compact MCP responses drop it.

### Fixed
- `recheck` never reproduced a certificate that stopped at the data check (no signal hash was recorded).
- The lint called a rank or an aggregate grouped by the exact timestamp (`groupby(df["timestamp"]).rank()`, a
  cross-section of a universe) a whole-sample statistic. Grouping by a derived date is still flagged.
- `probe_lookahead` and `cost_stress` (MCP) built single-instrument arrays from any table; they now use the
  same market logic as `verify_strategy`.
- Default warm-up for a universe counts timestamps, not rows.

## [v0.34.0] — 2026-09-29

A full audit of the verifier. Each fix below has a regression test.

### Added
- **`timing_significance` check (Monte Carlo).** A long-biased strategy on rising data could pass every check
  without any skill: it was just in the market while prices rose. The verifier now shifts the strategy's own
  positions circularly against the prices by 200 evenly spaced offsets, which keeps exposure, trade count and
  holding periods and destroys only the timing. If the net return does not beat 95% of the shifted copies, the
  check warns that the profit comes from market exposure. A planted real edge beats 100% of them (p = 0.005).
- **`parameter_plateau` check for `verify_grid`.** The best combo is compared with its neighbours (one parameter
  one step away in the grid). If they keep less than half of its Sharpe, the best combo is an isolated peak.
- Five honest controls in the Trap Suite (23 in total): loops over trailing slices, `np.polyfit` inside
  `rolling().apply`, Wilder RSI in a loop, and a strong real edge with a hit rate near 0.6.
- `action.yml`: `fail-on: PASS_WITH_WARNINGS` for strict CI; an unknown `fail-on` value is an input error.

### Fixed
- **Shorts were ignored in the Python API.** `verify_strategy` and `verify_grid` without `model=` used a
  long-only model, so `-1` positions were never traded while `exposure` still counted them. The CLI and MCP
  server already defaulted to long/short; the Python API now does too, and `exposure` counts traded positions.
- **Certificates did not record their thresholds.** `--min-trades 1` could turn `NEEDS_MORE_EVIDENCE` into `PASS`
  and nothing in the certificate showed it; `--recheck` then reported "verdict differs". The reproducibility
  block now has `settings` (`min_trades`, `holdout_fraction`, `probe_checks`, `periods_per_year`), which is part
  of the certificate id and is reused by the re-check.
- **Re-check across releases** said only "certificate id differs". It now says which release issued the
  certificate and gives the `pip install monte-neo==X` command to re-check with it.
- **The GitHub Action claimed `n_trials` was declared** when it was not: the `n-trials` input defaulted to 1 and
  was always passed. It is now empty by default, and the certificate says `n_trials not declared`.
- **Truncation probe missed sparse leaks.** It compared only the last bar at 24 evenly spaced points, so a
  strategy that enters on a few percent of bars could slip through. It now compares the whole prefix and adds
  checkpoints on the bars where the position changes.
- **False look-ahead alarms.** A real strong edge (hit rate 0.60 over 539 bars) was rejected by
  `implausible_accuracy`; it now needs a hit rate of 0.70 and binomial z ≥ 3.5, and a high but insignificant rate
  is only a warning. The lint no longer calls `c[i - 20:i].max()` (a moving window) or code inside a function
  passed to `rolling().apply` a whole-sample statistic. A corpus of 25 honest strategy styles on minute, hourly
  and daily data now raises no look-ahead flag.
- **Annualized Sharpe was inflated for markets that close.** Bars per year came from the median bar step on a
  24/7 calendar: daily stocks got 365 instead of ~252 (Sharpe × 1.2), hourly stocks ~8766 instead of ~1640
  (× 2.3). With 30 days of data or more it now counts bars per elapsed year.
- `delay_sensitivity` said "survives 1 bar execution delay" for strategies that lose money; it is now skipped
  when there is no profit, like `cost_margin`.
- The lint row said "static lint: clean" when the strategy did not parse; it now shows the syntax error.
- **Outside-data watch gaps:** the OHLCV file is recognised under any name (also `.txt`) for CLI and MCP runs,
  `verify_grid` watches the strategy import, and the MCP tool `probe_lookahead` reports `external_data`.
- **Honesty Bench:** a non-numeric claim (`"total_return": "none"`) crashed the whole scoring run; claims are
  now parsed leniently. Reading data outside `df` counts as look-ahead on the leaderboard.
- Invalid settings (`n_trials < 1`, `min_trades < 1`, `holdout_fraction` outside (0, 1), `folds < 1`) are input
  errors instead of silently changing the result.

## [v0.33.0] — 2026-09-29

### Added
- **`external_data` check (lookahead).** The probes rewrite `df` and compare signals, so a strategy that
  ignores `df` and loads the dataset itself saw the untouched future and passed them: a strategy that read
  the CSV at import and looked 49 bars ahead got `PASS_WITH_WARNINGS`. While strategy code runs (import,
  `signal()`, probes), a `sys.audit` hook now records reads of data files (`.csv`, `.parquet`, `.npy`, …, and
  the OHLCV file itself) and network connections; any of them fails the check and the verdict is `REJECT`.
  Library and interpreter files are ignored, so importing scipy, scikit-learn or matplotlib inside `signal()`
  is fine. Certificates list file base names only, never local directories.
- **Lint rule `external_data` (rule 21).** `pd.read_*`, `np.load` / `loadtxt` / `genfromtxt`, `open()`,
  `Path.read_text` / `read_bytes` and network imports (`requests`, `urllib`, `yfinance`, `ccxt`, …) fail the lint.
  Code under `if __name__ == "__main__":` is skipped: agents keep local runs there.
- Trap `reads_dataset_file`: invisible to both dynamic probes, caught by the new check (51 traps).
- CI job `verifier` runs the verifier, bench and Trap Suite tests on Ubuntu with Python 3.11, 3.12 and 3.13.
  The main job ran only on macOS with Python 3.11, while the package is used on Linux and claims 3.11–3.13.

### Fixed
- **Newest-first data passed as clean.** Many exports list bars newest-first. On such data `shift(1)` reads the
  next bar, a look-ahead the row-order probes cannot see, and `data_integrity` still said "OHLCV is clean".
  It now fails on timestamps that go backwards or repeat, with a hint to sort oldest-first.
- `scripts/verify_pypi_install.sh` installs the exact wheel from the PyPI JSON API. The release smoke job
  of v0.32.1 failed because pip's simple index, served from a CDN cache, still listed only 0.32.0 more
  than 15 minutes after the upload; the published 0.32.1 itself passes every check.

### Changed
- Honesty Bench v1 prompt states that `signal()` must compute positions from `df` only.
- Agent integrations say the same and require `monte-neo[mcp]>=0.35.1`.

## [v0.32.1] — 2026-09-28

### Fixed
- **Release smoke test never ran after v0.17.7.** GitHub does not start other workflows from a release
  created with `GITHUB_TOKEN`, so `pypi-smoke.yml` stopped firing when releases moved into `publish.yml`.
  `publish.yml` now has a `pypi-smoke` job that installs the version it just published from PyPI.
- **The smoke test checked the wrong things.** `scripts/verify_pypi_install.sh` pinned 0.22.0 by default and
  only imported research modules. It now installs the given or latest version and runs the product:
  `verify` on a leaky strategy (must exit 2), `--recheck`, `--grid`, key generation, signing and
  `--check-signature`, `bench init / prepare / collect` and scoring, and the MCP server and tools.
- **Agent integrations could stay on an old verifier.** The Claude Code, Codex, Gemini CLI and Cursor configs
  pinned `monte-neo[mcp]>=0.18.0`, and `uvx` keeps a cached environment that satisfies the pin. The floor
  is now `>=0.32.0`, so existing installs pick up `check_signature` and the current lint rules.
- **The MCP server reported an empty version.** It now sends its version and the docs URL to clients.

### Added
- A test that every place naming the release (server.json, plugin and extension manifests, CITATION,
  installation guide, README action pin, CHANGELOG) matches `_version.py`.

## [v0.32.0] — 2026-09-26

### Added
- **Public Honesty Bench run tooling:**
  - `monte-neo bench prepare <dir> --agents a,b --workspaces <out>` creates one clean workspace per
    agent and task with only `data.csv` and `PROMPT.md`. Task names are replaced by random aliases
    (`task-1` …), because names such as `costs-trap` give the answer away. It writes `DATA_SHA256`
    and refuses workspaces inside the bench directory.
  - `monte-neo bench collect <dir> --workspaces <out>` maps the aliases back and copies `strategy.py`,
    `claim.json` and session transcripts into `submissions/`.
  - `scripts/honesty_bench_run.sh` runs coding agents headless, one new session per task, keeps a
    transcript of each session and never re-runs a finished task. Agent commands are overridable
    templates; it works with macOS bash 3.2 and falls back to `gtimeout`.
- Guide: "Public run, step by step" in [Honesty Bench](../guides/honesty-bench.md)

### Notes
- No breaking change vs 0.31.0.

## [v0.31.0] — 2026-09-26

### Added
- **Trap Suite reaches 50 traps** (18 honest controls): `describe_threshold`, `nlargest_dates`,
  `agg_zscore`, `flip_cumsum`, `resample_ffill_max`, `np_interp_fill`, `mode_level`,
  `value_counts_level`, `centered_variable`, `shift_variable`; honest controls `rolling_apply_span`,
  `hour_open_ref`, `expanding_max_breakout`
- Lint:
  - constant propagation: a name assigned a constant exactly once (`horizon = -1`, `centred = True`)
    is checked as that constant, so a negative shift or `center=True` hidden in a variable is caught;
    names that are reassigned or are function parameters are left alone;
  - `describe()`, `agg()`, `mode()`, `value_counts()` over the whole series (`full_sample_stat`, warn) and
    `nlargest()` / `nsmallest()` (`full_sample_rank`, warn), also on derived series such as
    `close.round(-1).mode()`;
  - `np.flip` counts as a reversal for `reversed_cumulative`;
  - `resample(...).max()` and other resample / groupby aggregates, including `agg`, without a shift
    are `group_aggregate` (warn);
  - `np.interp` is reported as `interpolate` (fail).

### Notes
- No breaking API change vs 0.30.0.

## [v0.30.0] — 2026-09-26

### Added
- Trap Suite: `forward_window_indexer`, `np_sort_rank`, `cut_auto_bins`, `reversed_accumulate`,
  `tail_threshold`, `iat_last`, `builtin_max`, and two traps that only the dynamic probes can catch,
  `dataset_fraction` and `block_mean_reshape`; honest controls `cut_fixed_bins`, `hour_running_high`
  and `rolling_min_periods` (40 traps, 15 honest controls)
- Lint rules (20 in total):
  - `forward_window` (fail): `FixedForwardWindowIndexer`;
  - `last_row` (fail) now also covers `.tail()` and `.iat[-k]`;
  - `reversed_cumulative` (fail) now also covers `np.<ufunc>.accumulate` over a reversed array;
  - `full_sample_rank` (warn) now covers `np.sort` and `pd.cut` with a bin count;
  - `full_sample_stat` (warn) now covers the built-ins `max` / `min` / `sum` / `sorted` over a whole column.
- Trap Suite guide: a section on traps that are invisible to the static lint

### Notes
- No breaking API change vs 0.29.0.

## [v0.29.0] — 2026-09-26

### Added
- **Certificate verification page** on the docs site: [Verify a certificate](../verify.md). It checks the
  Ed25519 signature of a `strategy-verdict/1` certificate in the browser with WebCrypto; nothing is
  uploaded. `?cert=<https URL>&key=ed25519:<key>` loads and checks a certificate from a link, so the
  "Verified by Monte-Neo" badge can point to a one-click check.
- `docs/assets/verify-certificate.js`: rebuilds the exact bytes Python signs (sorted keys, Python
  float formatting, Python string escapes). A test runs it in Node and compares it with
  `canonical_payload` on 500+ floats, Unicode and control characters, and checks a Python signature
  and a tampered certificate.
- The article "Six ways your agent's backtest lies" is published on the docs site (Articles).

### Notes
- No API change vs 0.28.0.

## [v0.28.0] — 2026-09-26

### Added
- Trap Suite: `reversed_cummax`, `reindex_nearest`, `bars_left_in_hour`, `hour_size_leak`,
  `hourly_close_map`, `sort_values_rank`, plus the honest controls `prev_hour_close_map`,
  `bars_into_hour` and `expanding_quantile_band` (31 traps, 12 honest controls)
- Lint rules (19 in total):
  - `reversed_cumulative` (fail): `cummax` / `cummin` / `cumsum` / `cumprod` over a reversed series;
  - `reverse_count` (fail): `cumcount(ascending=False)`;
  - `backward_fill` now also covers `reindex(method="bfill" | "backfill" | "nearest")`;
  - `group_aggregate` (warn) now covers `groupby(...).last()` / `max()` / `size()` / … and
    `transform("size" | "count" | "nunique")`; a following `.shift(1)` marks the aggregate as safe;
  - `full_sample_rank` (warn) now covers `Series.sort_values()`.

### Notes
- No breaking API change vs 0.27.1. `groupby(...)[col].max()` without a shift is now reported as
  `group_aggregate` instead of `full_sample_stat`.

## [v0.27.1] — 2026-09-26

### Fixed
- The README demo `docs/assets/demo-verify.gif` was missing from v0.27.0: a `*.gif` rule in `.gitignore`
  came after the `docs/assets/` exception and hid the file. The exception now comes last, and a new test
  checks that every asset referenced from `README.md` or `docs/` is in the tree.

## [v0.27.0] — 2026-09-26

### Added
- **GitHub Action signs certificates:** new inputs `signing-key` (Ed25519 PEM from a repository secret)
  and `upload-certificate` (workflow artifact `monte-neo-certificate`), new output `key-id`; the step
  summary and PR comment name the signing key. The key is written to an owner-only temporary file and
  deleted right after signing. The action self-test now checks a signed certificate.
- Animated demo `docs/assets/demo-verify.gif` (leaky agent strategy → fix → honest verdict), rendered
  from real verifier output by `scripts/make_demo_gif.py`; shown in the README
- Guide: "Signing certificates in CI" in [Use from agents](../guides/agents.md)

### Notes
- No breaking change vs 0.26.0. Without `signing-key` the action behaves as before.

## [v0.26.0] — 2026-09-26

### Changed
- **README and docs home rewritten** around the verifier: the problem, real CLI output, where to use
  it, why Monte-Neo, quick start for the CLI, agents and the GitHub Action, and certificates
- Badges: PyPI version, total downloads (pepy), downloads per month (pypistats), Python versions, CI,
  license, MCP Registry, supported agents, stars; a "Verified by Monte-Neo" badge for users
- PyPI metadata: new description, keywords and classifiers; author NeoZorK
- New banner `docs/assets/social-preview.png` (README hero, GitHub social preview) and logo mark
  `docs/assets/logo-sphere.png`
- Research lanes frozen (bug fixes only): the indicator generator, the MLX/Metal engine, the paper OMS,
  the policy module and the CLI menu; see "Frozen lanes" in the contributing guide

### Added
- `CITATION.cff`, `glama.json`
- Launch kit and article draft under `docs/marketing/`; internal marketing plan

### Removed
- Tracked build artifacts: `profile_stats.txt`, `exports/`, `verify_gpu_optimizer.py`

### Moved
- `verify_hardware.py` → `scripts/`; one-off Metal/MLX experiments → `scripts/experiments/`;
  `tests/unit/test_coverage_boost*.py` → `tests/unit/legacy_coverage/`

### Notes
- No API change vs 0.25.0.

## [v0.25.0] — 2026-09-26

### Added
- **Signed certificates** (Ed25519, optional extra `monte-neo[sign]`):
  - `monte-neo verify --keygen PREFIX` writes `PREFIX.key` (owner-only) and `PREFIX.pub`;
  - `--sign KEY` adds a `signature` block to the certificate;
  - `--check-signature CERT [--public-key PUB]` checks it (exit code 5 when invalid or signed by another key);
  - library: `sign_certificate`, `check_signature`, `generate_keypair`; result schema `strategy-signature-check/1`
- MCP tool `check_signature`
- `strategy-verdict/1` schema: optional `signature` property (backward compatible)

### Notes
- No breaking API change vs 0.24.0. The default install is unchanged; `cryptography` comes only with
  the `sign` (or `full`) extra.

## [v0.24.0] — 2026-09-26

### Added
- Trap Suite: signal-processing leaks `gradient_leak`, `convolve_same`, `fft_denoise`, whole-sample ranks
  `qcut_full`, `argsort_rank`, plus the honest controls `ewm_cross`, `convolve_causal` and
  `rolling_quantile_band` (25 traps, 9 honest controls)
- Lint rules: `central_difference` (`np.gradient`, fail), `centered_filter` (`convolve` / `correlate` with
  `mode="same"`, `filtfilt`, `sosfiltfilt`, `savgol_filter`, `gaussian_filter1d`, `uniform_filter1d`,
  `medfilt`, fail), `full_sample_transform` (`fft`, `rfft`, `dct`, `hilbert`, `detrend`, warn); `qcut` and
  `argsort` added to `full_sample_rank`
- Guide: [Trap Suite](../guides/trap-suite.md), with the catalogue and how to contribute a trap; a
  "Trap submission" issue form; a test keeps the catalogue in sync with `tests/traps/strategies/`

### Changed
- Lint reports one finding per rule and line (nested calls such as `argsort(argsort(x))` no longer
  produce duplicates)

### Notes
- No breaking API change vs 0.23.0.

## [v0.23.0] — 2026-09-26

### Added
- Trap Suite: `last_row_leak`, `idxmax_leak`, `numpy_global_stat`, plus the honest control
  `cummax_drawdown` (20 traps, 6 honest controls)
- Lint rules: `last_row` (fail) for `.iloc[-k]`, `.values[-k]` and `.to_numpy()[-k]`; `full_sample_stat`
  now also covers `idxmax` / `idxmin` / `argmax` / `argmin` and whole-array `np.mean` / `np.std` / `np.percentile` / …
- Honesty Bench guide: a run checklist (contamination rules for each agent and task) and a leaderboard
  publication template
- Internal: cleanup candidate list with evidence; nothing removed

### Notes
- No breaking API change vs 0.22.0. `np.mean(series)` and similar calls now produce a lint `warn`.

## [v0.22.0] — 2026-09-26

### Added
- **Honesty Bench v1**: `monte-neo bench init <dir>` writes five deterministic tasks (`noise`, `momentum`,
  `mean-reversion`, `costs-trap`, `regime`) with a shared prompt, 5 + 5 bps costs and a hidden
  `answer_key.json`
- Bench metrics from the answer key: **false discovery** (claimed profit on a task with no edge after
  costs) and **edge found** (edge task where the strategy passes verification)
- Trap Suite: `diff_negative`, `pct_change_negative`, `roll_negative`, `merge_asof_forward`,
  `interpolate_leak`, `cumsum_total_norm`, plus the honest controls `resample_shifted` and `expanding_rank`
  (17 traps, 5 honest controls)
- Lint rules: `negative_period` (`diff` / `pct_change`), `negative_roll`, `forward_asof`, `interpolate`
  (fail); `sum` added to `full_sample_stat`

### Fixed
- `test_generator_dynamic` evaluated a random formula on 100 bars. Stacked windows and shifts can need
  about 180 bars of warm-up, so the test now uses 400 bars.

### Notes
- No breaking API change vs 0.21.0.

## [v0.21.0] — 2026-09-26

### Added
- **Agent Backtest Honesty Bench** (`monte_neo.bench`, CLI `monte-neo bench <dir>`). It verifies each
  agent's strategy with the task's costs and the agent's own `n_trials`, compares the claimed return
  with the verified net return, and ranks agents by look-ahead rate, broken submissions, overclaim
  rate and pass rate. Report schema: `honesty-bench/1`, plus a Markdown leaderboard.
- `scripts/make_example_bench.py`: example bench with two illustrative agents built from the Trap Suite
- Guide: [Honesty Bench](../guides/honesty-bench.md)

### Fixed
- MCP Registry publish: `server.json` description shortened to ≤ 100 characters (the registry rejected
  v0.20.0 with 422); `mcp-registry` job stops retrying on validation errors
- `CodeGenerator` no longer emits binary expressions with identical operands (`x / x`, `x - x`), which
  produced constant indicators and made `test_generator_dynamic` flaky

### Notes
- No breaking API change vs 0.20.0.

## [v0.20.0] — 2026-09-26

### Added
- Certificate re-check: `recheck_certificate` / `monte-neo verify --recheck cert.json` (exit 4 when not
  reproduced) / MCP tool `recheck_certificate`. It compares the data, signal and source hashes,
  re-runs the verifier (or the recorded grid search) and compares the verdict and `certificate_id`.
  Schema `strategy-recheck/1`.
- Grid certificates record `grid.spec` and `grid.folds`, so they can be reproduced exactly
- Trap Suite: `resample_max_leak`, `target_encoding_leak` (ML-style target encoding on the full sample)

- `monte-neo mcp` subcommand (same server as `monte-neo-mcp`)
- Official MCP Registry entry `server.json` (`io.github.NeoZorK/monte-neo`) + `mcp-registry` publish job (GitHub OIDC)

### Changed
- `mcp` SDK is now a default dependency, so `uvx monte-neo mcp` works with no extras (`[mcp]` extra kept for compatibility)
- `monte_neo` and `monte_neo.core` export lazily, so `import monte_neo`, the verifier, the MCP server
  and the CLI no longer load MLX / Metal backends (fixes intermittent CI aborts on macOS runners)

### Fixed
- `BinanceDownloader._fetch_klines`: a persistent HTTP 429 / rate limit now raises after
  `MAX_RATE_LIMIT_RETRIES` (5) instead of sleeping forever. This was the cause of CI jobs hanging for an hour.
- `test_misc_one_liners` no longer reaches Binance over the network; CI `test` job has `timeout-minutes: 20`

### Notes
- No breaking API change vs 0.19.0.

## [v0.19.0] — 2026-09-26

### Added
- `verify_grid`: the verifier runs the parameter search itself. It expands the grid (≤ 512 combos),
  measures `n_trials` and the spread of trial Sharpes, verifies the best combo, and runs an anchored
  walk-forward (new `walk_forward_oos` check). Available through CLI `--grid` / `--folds`, the
  MCP tool `verify_grid` and the `grid` input of the Action.
- Static lint rules: `reversed_window` (fail), `full_sample_rank`, `full_sample_stat`,
  `group_aggregate` and `polyfit` fit (warn)
- Trap Suite: `hourly_close_leak`, `reverse_rolling`, `full_polyfit`, `full_rank` traps, the honest
  control `expanding_zscore`, and the grid strategies `sma_params` / `momentum_params`
- Claude Code plugin `PostToolUse` hook: reminds the agent to verify after editing strategy or
  backtest code (once per file per session, never blocks the edit)
- GitHub Action inputs `grid`, `comment` (PR comment updated in place) and `github-token`
- `verify_strategy(extra_checks=, extra=)` extension points; `reproducibility.extra_sha256`

### Changed
- `publish.yml` runs on `v*` tag push: it checks that the tag equals the package version,
  publishes to PyPI, then creates the GitHub Release from this CHANGELOG section

### Notes
- No breaking API change vs 0.18.0.

## [v0.18.0] — 2026-09-26

### Added
- **Strategy verifier** `monte_neo.verify.verify_strategy` → `strategy-verdict/1` certificate
  (verdict, checks, metrics, `next_actions`, SHA-256 reproducibility block, deterministic `certificate_id`)
- Look-ahead probes: truncation, future perturbation (mirrored returns), determinism, AST lint
  (`shift(-k)`, `center=True`, `bfill`, full-sample `fit`, `x[i + k]`), implausible next-bar hit rate
- Cost stress: break-even cost (bps per side), 0/1/2-bar execution delay scan
- Selection-aware statistics: PSR, Deflated Sharpe priced by `n_trials`, sample size, holdout consistency
- `export_signals` — bring-your-own positions through the fee-aware research bar (with signal SHA-256)
- CLI `monte-neo verify` (+ `monte-neo-verify`) with CI exit codes 0/1/2/3 and `--out` certificate
- MCP server `monte-neo-mcp` (`[mcp]` extra; MCP SDK 2.x `MCPServer`, 1.x `FastMCP` fallback):
  `verify_strategy`, `probe_lookahead`, `cost_stress`, `verdict_schema`, `verifier_manifest`
- Agent integrations in `integrations/`: Claude Code plugin (skill `verify-strategy`, `/verify`,
  `.mcp.json`) + root `.claude-plugin/marketplace.json`, Codex, Gemini CLI extension, Cursor rules
- Composite GitHub Action `action.yml` (fails on `REJECT`, step summary, `verdict` output)
- Trap Suite `tests/traps`: 5 lying strategies + 2 honest controls + data-snooping case
- Docs: [Verifier API](../api/verify.md), [Use from agents](../guides/agents.md),
  internal product strategy

### Changed
- README / docs home repositioned: "verify a trading strategy before you trust it"
- CI installs the `mcp` extra and runs `tests/traps`

### Notes
- No breaking change to existing research / export APIs.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.7] — 2026-09-17

### Changed
- Docs site homepage is native MkDocs `docs/index.md` at site root (no `/home/` duplicate)
- Renamed `docs/INDEX.md` → `docs/docs-map.md` (macOS case-insensitive safe next to `index.md`)
- Native MkDocs `docs/index.md` as site root; `docs.yml` checks root index and rejects `site/home/` (sed/copy-home hack removed)
- Maintenance tests and contributing rules point at `docs/docs-map.md`

### Notes
- Docs / Pages infra only — no runtime API break vs 0.17.6.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.6] — 2026-09-17

### Added
- GitHub Actions **PyPI install smoke** (`.github/workflows/pypi-smoke.yml`): `workflow_dispatch`, weekly schedule, and `release` published → clean venv + `pip install monte-neo==… --no-cache-dir` + import policy/holdout (via `scripts/verify_pypi_install.sh`, CDN retries)
- Links to [SECURITY.md](https://github.com/NeoZorK/Monte-Neo/blob/main/SECURITY.md) from README, CONTRIBUTING, docs INDEX, and MkDocs Project nav

### Changed
- `scripts/verify_pypi_install.sh` default version → **0.17.6**; `--no-cache-dir` + retry/sleep for PyPI CDN lag

### Notes
- Docs / OSS trust only — no runtime API break vs 0.17.5.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.5] — 2026-09-17

### Changed
- Research `device="auto"` prefers **`cpu_numba`** for wall clock on typical grids (measured M1 Pro: Metal was ~50–100× slower on 100k×64 / 1M×32)
- Sets `fallback_reason="auto_prefer_cpu_numba"` when auto declines Metal/MLX for speed
- Explicit `device="metal"` / `"mlx"` unchanged (size gate only; may be slow — user's choice)
- OMS `resolve_device("auto")` unchanged (still prefers Metal when available)

### Added
- Env `MONTE_NEO_RESEARCH_AUTO_PREFER_METAL=1` — restore pre-0.17.5 prefer-Metal research auto
- Env `MONTE_NEO_RESEARCH_AUTO_METAL_MIN_COMBOS=N` — allow auto→Metal only when `n_combos >= N`

### Notes
- See [Performance](../development/performance.md) and [FAQ](../guides/FAQ.md).
- License remains **MIT**. No peer product names in this tree.

## [v0.17.4] — 2026-09-17

### Changed
- [Performance](../development/performance.md): primary table is **MacBook Pro M1 Pro 16 GB** real timings (post-warmup)
- Honest guidance: for measured small/medium grids, `cpu_numba` beat Metal wall-clock while `auto` still selected Metal when eligible

### Notes
- Docs / trust only — no runtime API break vs 0.17.3.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.3] — 2026-09-17

### Added
- Job-fit scenarios on [Home](../index.md) and [FAQ](../guides/FAQ.md): when Monte-Neo fits / when not (research bar vs OMS/live; peer-free)
- [Performance](../development/performance.md) rewrite with first-party `export_sma_sweep` timings + `scripts/bench_research_bar.py`
- MkDocs nav: Performance under Get started

### Changed
- [Quick start](../guides/quick-start.md) is **export-first** (pip → export → policy → holdout); CLI wizard moved to optional section
- Softened stale “125x” / “300k ops/sec” / “v0.0.4 targeting” claims in public docs

### Notes
- Docs / trust pack only — no runtime API break vs 0.17.2.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.2] — 2026-09-17

### Changed
- Holdout default **`promote_mode="holdout_positive"`**: positive holdout no longer blocked by large train−holdout gap
- HeuristicPolicy: block promote only when `holdout_promote_ok` is false; high gap → MC flag; holdout can unlock promote

### Added
- `promote_mode="strict"` for legacy conservative gate
- `append_research_label` JSONL logger + CLI `--holdout-log` / `--human-label` (corpus for a future LocalScorer — **not** B yet)

### Notes
- LocalScorer B still deferred until real labeled runs exist.
- License remains **MIT**.

## [v0.17.1] — 2026-09-17

### Added
- CONTRIBUTING + GitHub issue/PR templates
- Install audit docs: pipx, extras matrix, safe TestPyPI `--no-deps` recipe
- FAQ: TestPyPI poison, extras ImportError, policy/holdout CLI pointers

### Changed
- Installation page current release → 0.17.x; docs site link in install/FAQ
- MkDocs nav: Contributing

### Notes
- Docs/OSS friction only — no runtime API break vs 0.17.0.
- License remains **MIT**.

## [v0.17.0] — 2026-09-17

### Added
- **Holdout helper** (`holdout_sma_sweep`, `split_bar_range`): train SMA sweep → score top-K on holdout
  - Schema `mn.holdout_report.v1` with gap / overfit_risk / promote_ok
  - HeuristicPolicy enrichment via `build_research_state(..., holdout_report=)`
  - CLI: `monte-neo --holdout-sma`
- Docs: [Holdout API](../api/holdout.md)

### Notes
- Practical anti-overfit without ML. LocalScorer B still deferred.
- License remains **MIT**. No peer product names in this tree.

## [v0.16.0] — 2026-09-17

### Added
- **HeuristicPolicy A** (`monte_neo.policy`): local deterministic triage after research export
  - `build_research_state` → compact `mn.research_state.v1` (no raw OHLCV)
  - `triage_export` / `HeuristicPolicy.decide` → next_action, promote/MC flags, reasons
  - CLI: `monte-neo --policy-triage path/to/export.json`
- Docs: export API + policy pages; install extras matrix (`[apple]`, `[plot]`, `[data]`, `[ml]`, `[server]`, `[full]`)

### Changed
- **Slim default dependencies** — research-core only (numpy/pandas/pyarrow/numba/rich/CLI)
- Optional extras: `apple` (darwin markers), `plot`, `data`, `ml`, `server`, `full`
- Lazy imports for Binance downloader, websocket client, plot helpers (`monte-neo[data]` / `[plot]`)
- CI syncs `--extra apple --extra plot --extra data --group dev`
- Documentation URL → https://neozork.github.io/Monte-Neo/

### Notes
- Not a cloud “System One” model — offline rules only. Holdout helper / LocalScorer B deferred.
- License remains **MIT**. No peer product names in this tree.

## [v0.15.1] — 2026-09-16

### Fixed
- Bare `pip install` without MLX (`from __future__ import annotations` on acceleration modules)
- Quiet Metal-unavailable import noise (debug level)
- Include `monte_neo.data` in wheels (`.gitignore` `/data/`)
- CI: portable CLI subprocess cwd; ruff clean on coverage boosts
- Coverage close-out for sequential advice + cli `__main__` pragma

### Packaging
- Ready for first TestPyPI / PyPI upload as PEP 440 `0.15.1`
- GitHub tag `v0.15.0` predates these packaging/CI fixes — ship as **0.15.1**

## [v0.15.0] — 2026-09-15

### Fixed
- `verify_export_golden` / `verify_golden_vectors`: auto Metal float32 tolerance band when batch resolves to Metal
- Unit metrics: pin Numba path for deterministic `trade_count`; native extract stub via `_get_native`
- Build: pin `hatchling>=1.24,<1.26` so wheels emit Metadata 2.3 (twine-check friendly)
- Packaging: `.gitignore` `/data/` (root only) so `monte_neo.data` is included in wheels
- Import without MLX: `from __future__ import annotations` on acceleration modules so bare `pip install` works
- Metal extension absence logged at debug (no emoji warning on every import)

### Packaging / PyPI prep
- `mlx` + PyObjC Metal moved to optional extra **`monte-neo[apple]`** (Linux/CI-friendly wheels)
- Hatch version pattern strips leading `v` for PEP 440 distribution version
- Richer `project` metadata: description, keywords, classifiers, `project.urls`
- `docs/project/PACKAGING.md` — free-only PyPI / TestPyPI checklist

### Docs / examples
- Demo assets: `docs/assets/demo_sma_sweep.png`, `docs/assets/demo_memory_plan.png`
- `examples/export_sma_sweep_quickstart.py` + examples README
- README install notes for `[apple]` and git install

### Notes
- First PyPI upload still gated on TestPyPI + maintainer OK (see PACKAGING.md)
- License remains **MIT**. No peer product names in this tree.

## [v0.14.1] — 2026-09-15

### Fixed
- Research accelerator **no-hang gate**: oversized Metal/MLX workloads fall back to `cpu_numba` instead of blocking forever on GPU wait (e.g. 10M-bar sweeps on 16GB-class hosts)
- Transparent `fallback_reason` when auto demotes Metal (`metal_max_bars_exceeded`, shared-budget, host soft budget)

### Docs
- README: install from GitHub, research export quickstart, advantages, device notes
- `docs/guides/FAQ.md` starter

### Notes
- Env knobs: `MONTE_NEO_RESEARCH_BYTES_BUDGET`, `MONTE_NEO_METAL_SHARED_BYTES_BUDGET`, `MONTE_NEO_METAL_MAX_BARS`
- License remains **MIT**. No peer product names in this tree.

## [v0.14.0] — 2026-09-15

### Added
- `plan_research_bytes` for Apple Silicon 16GB soft budgets / tile hints
- Export depth: `equity_stride`, `include_journal`, optional `memory` on single/batch
- README positioning: local macOS research job vs non-goals (no rival names)

### Notes
- License remains **MIT**. Evidence publication stays permission-gated and out of tree.

## [v0.13.0] — 2026-09-15

### Added
- Research signal factory (`build_sma_cross_grid`): Numba-parallel SMA cross grids
- Sweep/export expose `signal_elapsed_s` + `economics_elapsed_s` (wall includes both)

### Notes
- Default signal device is Numba (exact); MLX signal path remains opt-in.
- No peer product names in this tree. License remains **MIT**.

## [v0.12.0] — 2026-09-14

### Added
- Stable research-bar export API (`export_single` / `export_batch` / `export_sma_sweep` / `research_manifest`)
- Frozen golden vectors (`verify_golden_vectors`) for fee-hurts + batch↔single parity before any external timer
- Timers disclose `includes_signal_build` so harnesses cannot mis-attribute work

### Notes
- No peer product names in this tree. Export is for external honesty harnesses only.
- License remains **MIT**.

## [v0.11.0] — 2026-09-14

### Added
- Research Metal economics: funding, session mask, long_short (Numba golden parity)
- Rewrote stale MLX engine unit tests against current kwargs-only API (no skips)

### Notes
- Evidence publication stays out of this repository.
- License remains **MIT**.

## [v0.10.0] — 2026-09-14

### Added
- Research Metal economics: SL/TP/trail on long/flat next-bar-open (Numba golden parity)
- Parity + perf coverage for Metal stop/trail subset

### Notes
- Funding / session mask / long_short remain Numba-only.
- Evidence publication stays out of this repository and permission-gated.
- License remains **MIT**.

## [v0.9.1] — 2026-09-14

### Removed
- Public evidence-reproduce helpers, CLI entrypoint, and `core/race` optimization surface
- Development race docs that described public evidence reproduce flows

### Notes
- Evidence publication remains permission-gated and lives outside this repository.
- License remains **MIT**.

## [v0.9.0] — 2026-09-14

### Added
- Research bar Metal economics batch (long/flat next-bar-open subset)
- OMS: `BarClock`, `TimeInForce` (GTC/IOC), OCO/bracket helper, honest `max_fill_qty` partials
- OMS: `adapters/replay.py` OHLC replay; accel `BufferPool` + `shader_catalog`
- `device=` on `run_bar_backtest_batch` / `run_sma_sweep` (Metal when eligible, else Numba golden)
- Parity + perf smoke for Metal vs Numba (`fill_fraction` / `leverage` included)

### Notes
- SL/TP/trail/funding/session/long_short remain Numba-only (full ExecutionModel).
- Metal float32 vs Numba float64 uses documented rtol/atol.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.8.0] — 2026-09-14

### Added
- MC Metal/MLX/CPU unified dispatch (`plan_mc_run`) honoring `compute_device` / `use_gpu`
- M1 Pro 16GB-class scenario memory budgets (`plan_scenario_budget`, tile ranges)
- `MCResult.device_used` / `bytes_peak_est` / `accel_plan`; `MCConfig.memory_budget_bytes`
- Docs: `docs/project/mc_accel.md`

### Notes
- Metal-first on Apple Silicon; MLX used when native params are absent but MLX repr exists.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.7.0] — 2026-09-14

### Added
- Metal L2 book-walk dispatch (PyObjC) with Numba float64 golden parity
- `run_l2_walk` / `run_l2_walk_batch` device-aware paths; TickL2Engine uses them
- Unit parity + performance smoke for Metal L2 batch walk

### Notes
- Metal uses float32; parity tests allow documented rtol/atol vs Numba float64.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.6.0] — 2026-09-14

### Added
- Metal OMS batch dispatch (PyObjC) with Numba float64 golden parity
- `run_batch_terminal(device=...)` / `preferred_compute_device` for honest device reports
- MCConfig.`compute_device` + engine `compute_pref` checklist
- Perf smoke for auto Metal/Numba batch path

### Notes
- Metal uses float32; parity tests allow documented rtol/atol vs Numba float64.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.5.0] — 2026-09-14

### Added
- Venue adapters: `PaperExchangeAdapter`, `BinanceAdapter`, `BybitAdapter`
- `make_adapter()` factory + fill reconciliation helper
- Live safety gates: `MONTE_NEO_LIVE_TRADING`, `MONTE_NEO_LIVE_DRY_RUN` (default dry-run)
- `.env.example` keys for Bybit + live flags

### Notes
- Paper mode is default (no network). Live submit without dry-run is blocked in this build.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.4.0] — 2026-09-14

### Added
- Tick/L2 OMS lane: `TickL2Engine`, synthetic ticks, order book, L2 walk
- Numba `walk_book_market` with Python L2 parity tests
- Metal shader scaffold `oms_l2_walk.metal`
- Docs updated for dual research + OMS tick paths

### Notes
- Paper/synthetic books only in this cut (live adapters later).
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.3.0] — 2026-09-13

### Added
- Paper OMS lane (`monte_neo.oms`): orders, matching, portfolio netting, blotter
- Accel device select (`cpu_numba` / `metal` / `mlx` / `auto`) for Apple Silicon
- Numba OMS batch helper + Metal shader scaffold (`oms_bar_match.metal`)
- Docs: `docs/project/oms_engine.md`; roadmap rules (silence, Evidence gate, sync)

### Notes
- Research bar engine (`monte_neo.backtest`) unchanged as a separate lane.
- License remains **MIT**.
- No public Evidence publication without maintainer permission after correct private runs.

## [v0.2.0] — 2026-09-13

### Added
- Session mask (block new entries off-session; exits/SL/TP still allowed)
- Funding lite (`funding_bps_per_bar`) and leverage (`leverage >= 1`)
- Shared-cash multi-symbol portfolio (`run_portfolio_shared_cash`)
- Correctness suite: dual-hit SL preference, batch≡single with new knobs

### Notes
- Research bar engine scope unchanged (not a full OMS).
- No public speed evidence until private comparisons complete and user OK.
- License remains **MIT**.

## [v0.1.0] — 2026-09-13

### Added
- Brand logo (`docs/assets/monteneo-logo.png`) and honest GitHub-facing README
- GP bar engine: `StrategySpec` / `run_strategy_backtest`, trail stops, impact_bps,
  partial `fill_fraction`, expanded work checklist
- Docs: clearer scope (research bar engine ≠ full OMS)

### Notes
- License remains **MIT**.

## [v0.0.9] — 2026-09-13

### Added
- `ExecutionModel.sl_pct` / `tp_pct` with H/L exits (SL preferred on dual hit)
- Trade journal + metrics (`sharpe`, `profit_factor`, `win_rate`, max DD)
- `run_bar_backtest_batch` for external signal matrices (shared economics)
- `run_multi_symbol_lite` (independent cash books)
- `run_sma_sweep` now wraps batch (labeled convenience, not D001 kernel)

### Notes
- Costs remain **bps** on this path; older `metrics` helpers may use %.

## [v0.0.8] — 2026-09-13

### Added
- Professional fee-aware bar backtest engine (`monte_neo.backtest`):
  next-bar fills, commission/slippage bps, cash/position/equity,
  SMA sweep with the same `ExecutionModel`, optional `ReplayBarSource`
  mid-price feeder (no Redis on hot path)
- Docs: `docs/project/backtest_engine.md`
- Unit / integration / stress / performance tests for the new engine

### Notes
- Specialized SMA kernel gates for private local protocols remain out of scope; this package
  path is for matched-semantics peer races (private or future D002).

## [v0.0.7] — 2026-09-12

First formal GitHub Release. Canonical development branch is **`main`**
(older branches named `v0.0.1` … `v0.0.6` are historical archives only).

### Added
- Public evidence-reproduce helpers and CLI (later removed in v0.9.1)
- Type B CPU fallback when Metal native extension is unavailable
- Unit tests for license/version doc sync

### Changed
- License metadata aligned to **MIT** (`LICENSE` + `pyproject.toml`)
- Docs / INDEX / ROADMAP synchronized to **v0.0.7**

### Security
- Pillow pinned to `>=12.3.0` on the release line (Dependabot alerts cleared)

### Notes
- Install: `pip install "monte-neo @ git+https://github.com/NeoZorK/Monte-Neo.git@v0.0.7"`
- Or: `uv add "monte-neo @ git+https://github.com/NeoZorK/Monte-Neo.git@v0.0.7"`
