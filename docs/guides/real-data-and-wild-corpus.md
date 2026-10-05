# Real data: Honesty Bench run, discover on real markets, wild scan

Every command on this page was run before it was written down: the bench pipeline end to end with a stand-in agent,
the scripts on synthetic files. What could not be run without your machine (the agent CLIs, downloads from the data
sites, `gh`) is marked *not run here*.

## 1. Honesty Bench v1: a public run

```bash
pip install monte-neo            # or: uv pip install monte-neo
monte-neo --version

monte-neo bench init hb-v1
shasum -a 256 hb-v1/tasks/*/data.csv > hb-v1/DATA_SHA256        # record the data hashes before the run
monte-neo bench prepare hb-v1 --agents claude-code,codex --workspaces ~/hb-v1-runs
```

`prepare` writes `~/hb-v1-runs/<agent>/task-1..task-5/` with only `data.csv` and `PROMPT.md`. Task names are hidden on
purpose; the map is `hb-v1/aliases.json`. Keep `hb-v1/answer_key.json` and `aliases.json` away from the agents (move them out
of reach for the run, put them back for scoring).

Check the agent commands before spending time:

```bash
MN_DRY_RUN=1 scripts/honesty_bench_run.sh ~/hb-v1-runs claude-code codex
```

This prints the command for every task and stops with an error if a CLI is not installed. The defaults are:

| Agent | Default command | Checked here |
|---|---|---|
| `claude-code` | `claude -p "$PROMPT" --permission-mode acceptEdits` | flags exist in Claude Code 2.1 |
| `codex` | `codex exec --full-auto "$PROMPT"` | *not run here* (not installed): run `codex exec --help` |
| `gemini-cli` | `gemini -p "$PROMPT" --yolo` | *not run here*: run `gemini --help` |
| `cursor` | `cursor-agent -p "$PROMPT" --force` | *not run here*: run `cursor-agent --help` |

If a flag changed, override it: `export MN_CMD_codex='codex exec --full-auto "$PROMPT"'` (dashes in the agent name become
underscores: `MN_CMD_claude_code`, `MN_CMD_gemini_cli`). Then run, collect, score:

```bash
scripts/honesty_bench_run.sh ~/hb-v1-runs claude-code codex
monte-neo bench collect hb-v1 --workspaces ~/hb-v1-runs
monte-neo bench hb-v1 --out hb-v1/report.json --markdown hb-v1/LEADERBOARD.md
```

The script runs each task once, in a new session, and never re-runs a task that has a `strategy.py` (the first final
answer counts). `LEADERBOARD.md` is the table; `report.json` keeps every certificate id for `monte-neo verify --recheck`.
Fair-play rules and the checklist are in the [bench guide](honesty-bench.md).

## 2. Discover on real markets

The sandbox this project is developed in cannot reach market-data sites, so the downloads are run on your machine. Both
sources need no key.

```bash
python scripts/fetch_market_data.py binance --symbol BTCUSDT --interval 1h --start 2021-01 --end 2024-12 --out data/real/btc_1h.csv
python scripts/fetch_market_data.py binance --symbol ETHUSDT --interval 1h --start 2021-01 --end 2024-12 --out data/real/eth_1h.csv
python scripts/fetch_market_data.py stooq --symbol spy.us --out data/real/spy_1d.csv
python scripts/fetch_market_data.py stooq --symbol gld.us --out data/real/gld_1d.csv     # not run here (no network)
```

Why these: Binance spot archives are free, long, hourly and 24/7 (the data has no sessions or splits); Stooq gives daily
ETFs, which are the opposite case (sessions, adjusted history). If Stooq answers with a page instead of a table (it sometimes asks for a captcha), download the file in a browser and give it the same columns: `Date,Open,High,Low,Close,Volume` becomes `timestamp,open,high,low,close,volume`. Many months of hourly data are about 35,000 bars per
symbol; ETFs have about 250 bars a year, so use the longest history.

```bash
monte-neo doctor data/real/btc_1h.csv          # known problems of the file first
python scripts/real_markets_run.py --out real-run data/real/btc_1h.csv data/real/eth_1h.csv data/real/spy_1d.csv data/real/gld_1d.csv
```

The runner calls `doctor` and `discover` for each file (budget 3000, 39 shuffled markets, lockbox 20 %, two generations
of evolution, costs 10 bp per side for the crypto files and 2 bp for the daily ETFs) and writes `real-run/SUMMARY.md`
and one folder per market with `strategy.py`, `result.json`, `search.jsonl`, `certificate.json` and `report.html`.
Expect "nothing found" on most real markets: that is the honest answer, and publishing the table with the best Sharpe a
plain search would have reported next to it is the point. A run on 35,000 hourly bars takes minutes to tens of minutes.

## 3. Wild scan: how many strategies in the wild have look-ahead patterns

Only aggregates leave your machine. The scan runs the verifier's static lint over strategy files you cloned and counts;
it records no file names, no repository names and no code.

```bash
gh search repos "freqtrade strategy" --language python --limit 100 --json fullName -q '.[].fullName' > repos.txt   # not run here
scripts/wild_clone.sh repos.txt ~/wild                                                                             # not run here
python scripts/wild_scan.py --out wild-report.md --json wild-report.json ~/wild
```

Repeat the search for `backtrader strategy`, `backtesting.py strategy` and `quantconnect algorithm`. The report lists
the files that look like strategies, the framework (from the imports), the share with a failing finding, the share with
only warnings and how often each rule fires. A finding is a place to look, not a proven leak; a clean file can still leak,
so say "contains a pattern that the lint flags" when you publish. Respect each repository's licence, and do not publish
names, links or code of the projects.

## 4. Why real Freqtrade and Lean runs

The adapters (`from_freqtrade`, `from_lean`, ...) turn what a framework wrote (a trades file, a results JSON) into the
positions the verifier reads. If that translation is wrong by one bar, or ignores shorts, fees or partial fills, the
verdict is wrong while every check looks fine. For vectorbt, Backtrader, backtesting.py, bt, Nautilus and Zipline the
tests run a backtest in the real framework and compare what the adapter reads with the position the framework itself held
at every bar. Freqtrade and Lean are tested only on files written by hand in their format, because running them needs a
Docker image (Lean), exchange-format data and their configuration. A real run closes that gap: one backtest in each
framework, exported, read by the adapter, and compared bar by bar with the framework's own equity curve. When you have the
environments, send me the exported files and I will turn them into tests.
