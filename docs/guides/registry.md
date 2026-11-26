# Try a public strategy in five minutes

The [Protocolith trading-strategy registry](https://github.com/Protocolith/trading-strategy-registry) publishes strategies together
with their evaluation: verdict, ARL, the gate they faced, and a hash-chained ledger that says what was frozen before the test.
`monte-neo registry` lets you **import** one, **try it yourself** (re-run the verification on public data), and **deploy it
locally** with [`monte-neo deploy`](deploy.md). You do not have to trust the registry's numbers; you can reproduce them.

## 1. Install

```bash
pip install monte-neo
monte-neo --version
```

Nothing else is needed: the registry client uses only the Python standard library.

## 2. List and look

```bash
monte-neo registry list                 # id, name, asset class, verdict, ARL, gate, importable, deployable
monte-neo registry list --deployable    # only records that can run on the Binance spot testnet
monte-neo registry show MN-TSM-CRY-002  # summary, evaluation, the gate and why, files, next commands
```

`--json` on `list` gives machine-readable output. Records without public code are listed but cannot be imported; `show` says why.

## 3. Import

```bash
monte-neo registry import MN-TSM-CRY-002
```

This writes `strategies/MN-TSM-CRY-002/` (or the folder in `--dir`) with `strategy.py`, `spec.json`, `record.json`,
`provenance.json` (URLs, hashes, ledger entry, import time) and a `README.md` with the next commands. `import` does not
verify anything, so it writes no `certificate.json`; `registry try` (step 4) runs the verification and writes it, and
`deploy init` needs that certificate.

## 4. Try it yourself

```bash
monte-neo registry try MN-TSM-CRY-002
```

It downloads the public Binance spot daily bars named in the record (cached in `strategies/MN-TSM-CRY-002/data/`), runs
Monte-Neo's verification of the strategy's `signal(df)` with the record's trial count and costs, writes `certificate.json`,
and prints your run next to the registry's: verdict, ARL, certificate id, Sharpe. `--start` and `--end` change the period.
Records with more than one symbol are not supported yet (exit code 2).

## 5. Deploy it locally

`try` ends with the exact command. Dry mode simulates the orders and needs no keys:

```bash
monte-neo deploy init --strategy strategies/MN-TSM-CRY-002/strategy.py \
  --certificate strategies/MN-TSM-CRY-002/certificate.json \
  --symbols BTCUSDT --rebalance daily --mode dry
monte-neo deploy run        # records every missing day up to today; safe to repeat
monte-neo deploy status
```

To use the Binance spot demo testnet, store testnet keys once (`monte-neo deploy keys`, see [deploy.md](deploy.md)) and start a new run
with `--mode testnet --run testnet`. Demo orders use play money. `deploy init` refuses a REJECT certificate, so a strategy that
fails your own run is not deployed.

## What is checked on import

- Every downloaded file must match its SHA-256 in `index.json`.
- The ledger must be an unbroken hash chain whose last hash equals the index's `ledger_head`.
- A ledger `record` entry must list the SHA-256 of both the record and the strategy code.
- A record marked not importable is refused with the reason from the index.

Any mismatch stops the import with exit code 3 and nothing is written. Exit codes: 0 ok, 1 the re-run failed,
2 not reachable or not supported yet, 3 a check failed or a usage error. Set `MONTE_NEO_REGISTRY` (or `--registry`) to a URL base or a
local clone to use another registry.

## What the numbers mean

The registry's numbers come from one verifier version on one data snapshot. Yours come from your installed version on
freshly downloaded bars, so the **Sharpe ratio should match closely, while the ARL and verdict can move** when the ARL rules or
the checks change between versions. A different verdict is information, not an error: read the reasons in `certificate.json`.
A verdict of `NEEDS_MORE_EVIDENCE` means the evidence is not yet enough, not that the strategy works. A gate that was not
passed is a result, and the registry publishes it on purpose.

## Limitations

- Binance spot daily bars only; one symbol per `try`; long-only; no futures or margin.
- Data revisions, exchange delistings and costs that differ from the cost model change the results.
- The strategy file runs with your permissions. Read it before you run it, as you would any code you download.
- Backtests and demo records are research examples. This is not investment advice and no promise of profit.

If this saved you time, please star the repository on GitHub: https://github.com/NeoZorK/Monte-Neo
