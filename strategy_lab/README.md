# Strategy Lab

A reproducible pipeline that finds and honestly verifies example strategies with Monte-Neo. Idea author: Claude Sonnet 5.5.
Process, design and verification: Rostyslav Shcherbyna. **Not investment advice.** Nothing here trades; no keys, no paper or testnet.

Round 1 (ten ideas, validation 2023-2024 only; archived in `results_round1/`, none passed the gates) and round 2 (below) live in `examples/strategies/<name>/` (`strategy.py`, `card.md`, generated `report.md`): time-series momentum,
SMA trend, Donchian breakout, RSI(2) and Bollinger mean reversion, volatility-targeted trend, cross-sectional momentum,
a BTC/ETH pair (perpetuals, with `--legs` and `--null-test`), funding carry, turn-of-month seasonality.

## Rules against self-deception

- Time is cut (fixed 2026-11-08, BEFORE any round-2 run) into **discovery 2017-08 to 2020-12** (includes the 2018 bear market, the 2019 range and the
  2020 crash and recovery), **validation 2021-01 to 2024-12** (2021 bull, 2022 bear, 2023-24 recovery) and a **sealed holdout 2025-01 on**
  (the newest piece, never read before one frozen candidate). Round 1 had validation 2023-2024 only (one bull regime); the new split is wider
  and puts a bear market in both discovery and validation. Honest caveat: 2023-24 was already seen in round 1, so round-2 ideas are
  fixed a priori from the literature and the old results, not from a fresh blind window; the holdout is the only blind data.
- Universe: 18 liquid USDT coins (today's survivors: **survivorship bias**, declared in every card and flagged by the verifier) and 12 perpetuals for carry/pairs.
- Costs (round 2): Binance taker fees by tier (default VIP0: spot 10 bps, perpetual 5 bps) plus a per-coin spread/slippage of 2-12 bps
  (`examples/strategies/_common/binance_costs.py`); every result is also computed with the costs doubled; the gate requires a positive net Sharpe in both.
- Parameters are fixed a priori in `META["params"]`. The declared grid only checks the plateau; every point is a trial.
- `n_trials` of the validation and holdout certificates is the number of variants declared **anywhere in the Lab**
  (all grids of all ideas), so picking the best of ten ideas is paid for in the deflated Sharpe.
- Each hypothesis is written to the registry before testing; every verification is appended to the hash-chained ledger.
- The holdout opens once, only for a candidate frozen in a git commit (`freeze.py`); `run_all.py --stages holdout` refuses otherwise.
  A candidate that fails is published as a reviewed case. Nothing is tuned afterwards.
- Raw series are never committed (git-ignored). Only metrics, verdicts and hashes are published (`results/`).

## Round 2: ideas (pre-registered before running)

Trend basket (vol-scaled TSMOM, Donchian channel position) over 18 coins; BTC-neutral long-short (residual momentum, trend vs market);
short-term mean-reversion basket; funding carry v2 with per-coin costs. Signal ideas go through `monte-neo alpha` (with `--aum`, point-in-time
membership and the default factor attribution), the only path that can reach ARL 5-7; carry is a return series and its ARL is
capped by construction (the Lab adds the integrity check of the input prices and labels the scope). Per idea: `card.md`, an automatic
`report.md` (with independent cost-aware economics: BTC correlation and beta share, alpha t-statistic vs BTC, cost x2 Sharpe, Sharpe by calendar year)
and one row in `results/summary.json` (ARL, deflated Sharpe, timing p, beta share). Pairs: `--pairs-checks` is used when the CLI has it
(branch x/laughing-morse-208e19); otherwise the report says so and a pair cannot pass the gates.
`n_trials` counts every grid point of every idea of both rounds.

## Run it (one command)

```bash
uv run python scripts/strategy_lab/lab.py                      # interactive: live table, progress, ETA, RAM/CPU/disk/power, keys
```

Under `nohup` or over ssh (for example on `mbp2014`), no terminal needed:

```bash
mkdir -p strategy_lab/logs
nohup uv run python scripts/strategy_lab/lab.py --plain > strategy_lab/logs/lab.out 2>&1 &
tail -f strategy_lab/logs/lab.out
```

`lab.py` downloads the data (resumable, SHA-256 checked), then runs prepare, discovery and validation for all ideas, restarts a
crashed step (up to 20 attempts without progress), picks `--jobs/--threads` from RAM and cores (override with the flags), and prints
the summary when everything before the holdout is finished. Keys: `r` run, `p` pause, `x` safe stop, `f` retry failed, `a` analyze,
`l` longer log, `h` holdout, `q` quit. Ctrl-C is a safe stop; after a crash, a power cut or a closed terminal just start the same
command again. Only one instance runs at a time. The holdout never starts by itself.

Check the tooling before a long run: `uv run python scripts/strategy_lab/lab.py --dry-run` (whole pass on synthetic stubs in a scratch
folder, never in `results/`) and `--self-test` (dry-run with `kill -9` of the child and of `lab.py`, then resume).

The older scripts (`fetch_data.py`, `run_all.py`, `analyze.py`, `watchdog.sh`) are the internal steps `lab.py` drives and still work alone.

Freeze and open the holdout, one idea at a time, only if its validation gate is open:

```bash
python scripts/strategy_lab/freeze.py NAME
git add examples/strategies/NAME strategy_lab/results/NAME && git commit -m "freeze NAME"
python scripts/strategy_lab/run_all.py --stages holdout --only NAME   # or: lab.py, key h (asks you to type a confirmation)
```

## Track 2: ETFs and indices with long history (pre-registered 2026-11-09, BEFORE any ETF series was downloaded or looked at)

Reason: statistical power comes from long data across markets, not from more variants on four years of crypto.

- Date split, fixed now: **discovery up to 2014-12-31** (includes 2000-02 and 2008 for the assets that exist then), **validation 2015-01-01 to 2020-12-31**
  (2015-16 range, 2018 drawdown, 2020 crash and recovery), **sealed holdout 2021-01-01 on** (2022 bonds+stocks drawdown, newest data; never read before one frozen candidate).
  Crypto holdout 2025+ is unchanged. The downloader writes the sealed part into separate files that the loader never opens without a freeze commit.
- Universe, fixed now (16 US-listed ETFs, today's survivors, declared in every card): SPY QQQ IWM EFA EEM TLT IEF SHY LQD HYG GLD SLV DBC USO UUP VNQ.
  Inception dates differ (the panel grows with time; an asset is used only from its first full year). Source: Yahoo chart API (close and adjusted close, daily); series are never committed.
- Ideas, canonical literature parameters, fixed in `scripts/strategy_lab/etf_ideas.py` and `strategy_lab/batches/etf_prereg.json` (committed before the download):
  time-series momentum with volatility targeting (Moskowitz-Ooi-Pedersen), cross-asset momentum (12-1, top third), inverse-vol risk parity,
  bond trend plus carry (carry = trailing distribution yield), dual momentum (Antonacci). 16 grid points in all, used only to check the plateau.
- Costs: 3 bps per side (commission + half spread), also run at 2, 5 bps and with costs doubled; short borrow 50 bps a year; leverage capped at 1.0 (no financing); signals at the close of day t, trades on day t+1 (next bar).
- `n_trials` for the ETF certificates = the ETF grid points + every crypto variant of the Lab (all rounds). Verification through Monte-Neo (`verify_returns` / `alpha` / `research`), ARL by `arl-rules/1`.
- Nothing is tuned after the first look at validation; a failed candidate is published as a reviewed case.

## Track 3: forward record (no trading, no keys)

From **2026-11-10** `scripts/strategy_lab/forward_record.py` records once a day, on public data, the signals and HYPOTHETICAL positions of a list of candidates
frozen in `strategy_lab/forward/frozen.json` (SHA-256 of the code, the strategy files and the parameters; `run` refuses if anything differs).
It is neither a paper-trading account nor a testnet: no orders, no exchange account, no keys. The journal `strategy_lab/forward/journal.jsonl` is hash-chained;
a missed day is filled on the next run and flagged `late`.

- Crypto alpha: r4_b4_2, r4_b3_1, r4_b2_1, r4_b1_5 (long top third / short bottom third of the point-in-time liquid set, 3-day rebalance; the BTC hedge is not modelled).
- Carry E_pit (BTC..SOL pool, weekly decisions). Funding comes from OKX as a PROXY: fapi.binance.com is not reachable from the owner's location and the Binance bulk archive has funding only per finished month.
- ETF: risk parity, bond trend + carry, time-series momentum (the three best by validation Sharpe / discovery DSR; none passed the gates, they are recorded as forward evidence only).
- Crypto warm-up history is fetched from 2025-10-01 because the signals need 365-day windows. It is input only; no performance is computed on any date before the start day, and the
  crypto sealed holdout (2025+) of the historical candidates is not evaluated.
- Daily run and launchd: `scripts/strategy_lab/forward_daily.sh`; a launchd plist is prepared in `scripts/strategy_lab/launchd/` (not installed).
