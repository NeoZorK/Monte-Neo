# Deploy a verified strategy as a forward record

`monte-neo deploy` runs a strategy that Monte-Neo has already verified as a **forward record** on the Binance spot
**demo (testnet)**, and keeps an evidence journal that anyone can check. It answers a different question than `verify`: not
"is the backtest honest?" but "does the same rule keep working on days that did not exist when it was fixed?".

It is not live trading and not investment advice. Demo orders use play money; the profit and loss you see is measured at
**mainnet prices** with a stated cost model.

## What you get

- **An evidence journal**: an append-only, hash-chained JSON-lines file (`journal.jsonl`). Every signal input digest,
  order, fill, daily mark, kill switch and deviation is one line; a changed, removed or reordered line breaks the chain and
  `monte-neo deploy verify` names it. Writes are fsync'ed; a power cut leaves at most one incomplete last line, which `run`
  moves aside and records (never silently drops).
- **Two virtual books replayed from the journal**: a paper book (mainnet prices plus the cost model) and a testnet book
  (the real demo fills). Their difference is the tracking error.
- **A dashboard**: one static HTML page, inline SVG, no scripts and no CDN, served read-only.
- **Daily RFC 3161 anchors** of the journal head from a public time-stamping authority (only a hash leaves your machine).
- **An evidence report** with a manifest of every number and a `--verify` that recomputes them.
- **A Monte-Neo verdict on the forward returns** (`certify`), computed in-process with `verify_returns`.

## Eligibility

`init` refuses to start unless:

1. You pass a Monte-Neo **certificate JSON** (`--certificate`) whose verdict is **not REJECT**. Its id, verdict, ARL (if
   present) and the SHA-256 of your strategy file are written into the start entry. `NEEDS_MORE_EVIDENCE` is accepted with a
   warning in the journal.
2. If the certificate carries a source hash, it must match your strategy file. If it has none (for example a returns-only
   certificate), the journal records a warning that the pairing was not proven.
3. The settings are supported: Binance **spot**, **long-only**, no leverage, **daily or weekly** rebalance, USDT pairs.
   Anything else is refused with a message.

The strategy file is copied into the run folder and its hash is checked on every `run`. If the copy changes after start,
the run stops: begin a new run instead.

## The strategy plug-in

Your file defines one function:

```python
def target_weights(closes_by_symbol: dict[str, list[float]]) -> dict[str, float]:
    """Weights of TOTAL capital per symbol: long-only, each 0..1, sum <= 1. The rest stays in cash."""
    out = {}
    for symbol, closes in closes_by_symbol.items():
        out[symbol] = 0.5 if len(closes) > 50 and closes[-1] > sum(closes[-50:]) / 50 else 0.0
    return out
```

`closes` are complete daily closes, oldest first; the last bar closed before the day being recorded (no look-ahead). The
output is validated on every call: a non-dict, an unknown symbol, a negative or non-finite weight, a weight above 1 or a sum
above 1 stops the run with a clear error. The file is loaded with the same loader as `monte-neo verify --strategy`, so it
runs with your permissions: deploy only code you would run yourself.

## Quick start (no keys, no orders)

```bash
monte-neo verify --ohlcv data.csv --strategy my_strategy.py --out cert.json
monte-neo deploy init --strategy my_strategy.py --certificate cert.json \
    --mode dry --symbols BTCUSDT,ETHUSDT --first-day 2026-10-01
monte-neo deploy run          # records every missing day up to today; run it again any time, it is idempotent
monte-neo deploy status       # metrics and the journal check as JSON
monte-neo deploy serve        # dashboard on http://127.0.0.1:8787/
```

Modes: `dry` simulates the exchange and fills at the price of the day it replays (no keys, public market data only),
`paper` records only the paper book, `testnet` also sends demo orders. Useful settings: `--rebalance daily|weekly`
(`--weekday monday` by default), `--fee-bps 10 --slippage-bps 5` (per side), `--kill-drawdown -0.15` (the paper book
liquidates and stops at that drawdown from its peak), `--capital 10000`, `--var DIR` (where the journal lives, default
`./var`) and `--run NAME` (one folder per run). `--target local` is the only target that works now; `ssh`, `aws` and `gcp` are
accepted names that exit with "not available yet" (code 2).

Days that were missed are recorded late (`late: true`), never back-filled silently.

## Testnet keys

Create spot testnet keys at <https://testnet.binance.vision/> (these are not mainnet keys). Keys are looked up in this order:

1. the environment: `MONTE_NEO_TESTNET_KEY` and `MONTE_NEO_TESTNET_SECRET`;
2. the macOS Keychain: `security add-generic-password -s monte_neo_testnet_key -a monte-neo -w '<key>'` and the same for
   `monte_neo_testnet_secret`;
3. consented discovery: `monte-neo deploy keys` scans a few known places for files that define a Binance key and secret,
   shows file and variable names only, asks per candidate, checks the pair against the **testnet** endpoint only (a mainnet
   key fails there, so a live account cannot be wired in by mistake) and stores a working pair in the Keychain.

`monte-neo deploy keys --status` says where keys come from and whether the testnet accepts them. Values are never printed,
logged or journaled. Orders carry a deterministic client order id and are looked up before they are sent, so a retry never
sends one twice; fills of an order found by id are read from the account's trades.

## Run it every day

`scripts/deploy_loop.sh start` keeps a loop in a `screen` session: record every missing day, anchor the journal head,
rebuild the dashboard, then sleep until 00:10 UTC (the daily bar has closed); a failure retries in one hour. Also `status`,
`stop`, `serve [PORT]` and `logs`. Settings come from the environment (`DEPLOY_RUN`, `DEPLOY_VAR`, `DEPLOY_HOST`). The
journal is never touched by `stop`, and a restart resumes where it stopped.

## LAN dashboard

`monte-neo deploy serve` binds to `127.0.0.1` by default. To read it from another machine on your network:

```bash
monte-neo deploy serve --host 0.0.0.0 --port 8787      # or: DEPLOY_HOST=0.0.0.0 scripts/deploy_loop.sh serve
```

The server answers GET only and serves one folder (the generated page). There is no authentication: keep it behind a firewall
or a VPN.

## Evidence journal, anchors, report

- `monte-neo deploy verify` checks the chain and that the strategy copy still matches the start entry (exit 1 otherwise).
- `monte-neo deploy anchor` writes one RFC 3161 timestamp per day (`<run>/anchors/<date>.{txt,tsq,tsr}`) and journals it. It uses
  `openssl ts` and tries freetsa.org, then timestamp.digicert.com, then timestamp.sectigo.com. Check a reply later with
  `openssl ts -verify`.
- `monte-neo deploy certify [--n-strategies N]` runs Monte-Neo's returns verification on the recorded paper returns against a
  buy-and-hold benchmark of the same symbols. `N` defaults to the certificate's `n_trials` from `init`, so the search you paid
  for in the backtest is paid for again here. It needs enough days (the returns check wants at least 24 observations).
- `monte-neo deploy report` writes `report/report.html` and `report/report_manifest.json`. Stress replays run the frozen
  strategy on historical windows and are labelled as backtests, never mixed with the recorded period. Defaults are three
  public crypto stress windows; set your own with `--stress "NAME=2022-04-25:2022-07-15"` (repeatable) or skip them with
  `--no-stress`. `monte-neo deploy report --verify` recomputes every number and lists any difference.

## Limitations

- **Demo execution is not live.** Testnet order books are thin and Binance resets the testnet periodically; demo fills prove
  that the process works, not the slippage of a real account. A reset does not touch the virtual testnet book (it is replayed
  from the journal).
- **P&L is measured at mainnet prices with the cost model** (`--fee-bps`, `--slippage-bps` per side), not at the demo's fills.
  The report also shows Sharpe with those costs paid twice.
- Spot and long-only; daily or weekly rebalance; Binance only (venue risk is not diversified).
- A short forward record says little by itself. Read the verdict of `certify` for its significance, not the raw return.
- The journal proves nothing was edited after the fact; it cannot prove that you did not run other strategies in other runs.
  Keep every run folder.

Not investment advice. Monte-Neo does not recommend any strategy or trade.
