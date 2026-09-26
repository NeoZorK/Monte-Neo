# Monte-Neo

<!-- mcp-name: io.github.NeoZorK/monte-neo -->

<p align="center">
  <img src="docs/assets/monteneo-logo.png" alt="Monte-Neo logo" width="120"/>
</p>

<p align="center">
  <strong>Verify a trading strategy before you trust it.</strong><br/>
  Look-ahead probes · fee-aware next-bar economics · Deflated Sharpe · MCP server for coding agents<br/>
  MIT · Python 3.11+ · Numba (Metal / MLX optional)
</p>

<p align="center">
  <a href="https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml"><img src="https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <a href="https://pypi.org/project/monte-neo/"><img src="https://img.shields.io/pypi/v/monte-neo.svg" alt="PyPI"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"/></a>
  <a href="https://github.com/NeoZorK/Monte-Neo/releases/latest"><img src="https://img.shields.io/github/v/release/NeoZorK/Monte-Neo?label=release" alt="Latest release"/></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"/>
</p>

> Current: **v0.22.0** · [Docs site](https://neozork.github.io/Monte-Neo/) · [Verifier API](docs/api/verify.md) · [Agents](docs/guides/agents.md) · [Changelog](docs/project/CHANGELOG.md)

## What this is

Coding agents can now turn a trading idea into a backtest in minutes. Those
backtests often fail in the same ways:

- they read future bars (look-ahead);
- they ignore fees and slippage;
- they report the best of hundreds of tried variants.

**Monte-Neo is an independent verifier.** An agent, a CI job or a human calls it before
claiming that a strategy works. It returns a verdict (`PASS`, `PASS_WITH_WARNINGS`,
`NEEDS_MORE_EVIDENCE` or `REJECT`), the checks behind it, concrete `next_actions` and a
reproducible `strategy-verdict/1` certificate.

```text
$ uv run python examples/verify_quickstart.py
leaky: REJECT  certificate b4dfa9beee5515d2
  lookahead_truncation     lookahead   fail  truncation probe: LEAK DETECTED
  lookahead_perturbation   lookahead   fail  future-perturbation probe: LEAK DETECTED
  lookahead_static_lint    lookahead   fail  static lint: negative_shift
  implausible_accuracy     lookahead   fail  next-bar hit rate 1.000
  net_profitability        economics   fail  net total return -41.26% after costs
  deflated_sharpe          statistics  fail  deflated Sharpe 0.000 over 10 trial(s)
  -> The signal at bar t changes when later bars are removed: compute features only from rows <= t ...
causal: REJECT  certificate cc4c852ef6c99626
  net_profitability        economics   fail  net total return -3.88% after costs
  ...
```

Both strategies run on a synthetic random walk, so neither has a real edge. The leaky
one is caught by all four look-ahead checks. The causal one is never accused of
look-ahead: it is rejected only because it loses money after costs.

| Check family | What it catches |
|--------------|-----------------|
| **Look-ahead** | Truncation and future-perturbation probes, AST lint (`shift(-k)`, `center=True`, `bfill`), implausible hit rate |
| **Economics** | Losses after fees and slippage, thin break-even cost, edge that disappears with one bar of delay |
| **Statistics** | Deflated Sharpe priced by `n_trials`, sample size, holdout consistency |
| **Integrity** | Broken OHLCV, non-deterministic signals |

**Works where agents work:**

- MCP server `monte-neo-mcp`, for Claude Code (plugin), Codex, Gemini CLI, Cursor or any MCP client;
- CLI with CI exit codes;
- GitHub Action;
- Python API.

See [Use from agents](docs/guides/agents.md).

**Not a goal:** replace live-trading platforms. The verifier checks backtest methodology,
not future profit. It is not investment advice.

## Why Monte-Neo

| Advantage | What you get |
|-----------|----------------|
| Deterministic verdicts | Same data, code and `n_trials` give the same `certificate_id` |
| Trap Suite | `tests/traps`: known ways backtests lie, each with its expected verdict |
| Fee-aware research bar | Next-bar fills, costs in bps, SL/TP/trail, funding, sessions |
| Honest export API | `export_signals` / `export_single` / `export_batch` / `export_sma_sweep` + golden vectors |
| Anti-overfit research | Holdout, walk-forward, CSCV/PBO, Monte Carlo helpers, `HeuristicPolicy` triage |
| Local and private | Runs on your machine; no data leaves it |
| MIT | Use, fork and ship without drama |

## Install

**From PyPI (recommended):**

```bash
pip install monte-neo                 # research-core (slim)
pip install "monte-neo[mcp]"          # MCP server for coding agents (monte-neo-mcp)
pip install "monte-neo[apple]"        # Metal / MLX (Apple Silicon)
pip install "monte-neo[plot]"         # charts
pip install "monte-neo[data]"         # Binance downloader / websocket
pip install "monte-neo[full]"         # kitchen-sink local parity
```

**From git:**

```bash
pip install "git+https://github.com/NeoZorK/Monte-Neo.git"
pip install "monte-neo[apple] @ git+https://github.com/NeoZorK/Monte-Neo.git"
```

**In-repo (contributors):**

```bash
git clone https://github.com/NeoZorK/Monte-Neo.git
cd Monte-Neo
uv sync --extra apple --extra plot --extra data --group dev
```

See [PACKAGING.md](docs/project/PACKAGING.md) · [Export API](docs/api/export.md) · [Policy triage](docs/api/policy.md).

**Requirements:** Python **3.11+** on macOS or Linux. The verifier and research bar run on
Numba CPU. Metal and MLX are optional (`[apple]` extra).

## Quick start: verify a strategy

```python
from monte_neo.verify import verify_strategy

report = verify_strategy("btc_1h.csv", strategy="my_strategy.py", n_trials=12)
print(report["verdict"], report["certificate_id"], report["next_actions"])
```

`my_strategy.py` defines `signal(df)`, which returns one position per bar: `+1` long,
`0` flat, `-1` short. Details: [Verifier API](docs/api/verify.md).

## Quick start: research engine

```bash
uv sync --extra apple --extra plot --extra data --group dev
uv run monte-neo
uv run pytest tests -n auto
# After an export_sma_sweep JSON:
# uv run monte-neo --policy-triage path/to/export.json
```

### Research export (recommended)

```python
from monte_neo.backtest import (
    ExecutionModel,
    export_sma_sweep,
    synthetic_ohlcv,
)

ohlc = synthetic_ohlcv(100_000, seed=42)
model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
out = export_sma_sweep(
    ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"],
    combos=16,
    model=model,
    device="auto",  # Metal when safe; else cpu_numba (see fallback_reason)
)
print(out["device"], out.get("fallback_reason"), out["combos"])
```

### Single bar backtest

```python
from monte_neo.backtest import (
    ExecutionModel,
    frame_to_ohlc,
    run_bar_backtest,
    sma_signal,
    synthetic_ohlcv,
)

ohlc = frame_to_ohlc(synthetic_ohlcv(5_000, seed=42))
model = ExecutionModel(
    commission_bps=5.0,
    slippage_bps=5.0,
    size_fraction=0.25,
    sl_pct=1.0,
    tp_pct=2.0,
)
sig = sma_signal(ohlc["close"], fast=10, slow=40)
out = run_bar_backtest(
    ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
)
print(out["total_return"], out["metrics"]["max_drawdown"], len(out["trades"]))
```

More: [docs/guides/quick-start.md](docs/guides/quick-start.md) · [backtest engine](docs/project/backtest_engine.md) · [FAQ](docs/guides/FAQ.md)

## How to use (research workflow)

1. Load or synthesize OHLCV (`synthetic_ohlcv` / your frame → `frame_to_ohlc`).
2. Set an `ExecutionModel` (fees, SL/TP, sessions, side mode).
3. Sweep with `export_sma_sweep` / `export_batch`, or a single `export_single`.
4. Check `device`, `signal_device`, and `fallback_reason` when using `auto`.
5. Optional depth: `equity_stride`, journal, `plan_research_bytes` / `memory` on exports.
6. Paper OMS (`monte_neo.oms`) only when you need event-lane validation — not for sweep cps claims.

**Devices:** `auto` · `metal` · `cpu_numba` (and MLX where signal paths allow). Oversized Metal
jobs demote to Numba instead of hanging (v0.14.1+).

## Features (honest)

| Area | Status |
|------|--------|
| Strategy verifier + MCP server | `monte_neo.verify` / `monte-neo verify` / `monte-neo-mcp` |
| Agent integrations | `integrations/` (Claude Code plugin, Codex, Gemini, Cursor) + `action.yml` |
| MC indicator / robustness workflows | Available via CLI and library |
| Fee-aware research bar engine | `monte_neo.backtest` |
| Research export + golden vectors | `export_*` / `verify_golden_vectors` |
| Memory / no-hang accelerator gate | `plan_research_bytes` / `decide_research_accelerator` |
| Paper OMS + venue adapters | `monte_neo.oms` |
| Metal / MLX / Numba device select | Best-effort on Apple Silicon; CPU fallbacks |
| Docker | Supported for headless/CI-style runs |

## Project structure

```
Monte-Neo/
├── src/monte_neo/
│   ├── verify/        # Strategy verifier (look-ahead, costs, Deflated Sharpe)
│   ├── mcp/           # MCP server for coding agents
│   ├── backtest/      # Research bar engine + export
│   ├── oms/           # Paper OMS + accel
│   ├── core/          # Generator / Metal bridges
│   ├── data/          # Market data downloaders
│   ├── monte_carlo/   # MC methods
│   ├── metrics/       # Trading metrics
│   ├── cli/           # Interactive CLI
│   └── visualization/
├── integrations/      # Claude Code plugin, Codex / Gemini / Cursor configs
├── tests/             # unit, integration, traps (verifier Trap Suite)
├── docs/
└── docker/
```

## Screenshots / demos

<p align="center">
  <img src="docs/assets/demo_sma_sweep.png" alt="SMA sweep demo" width="720"/>
</p>
<p align="center">
  <img src="docs/assets/demo_memory_plan.png" alt="Memory plan demo" width="720"/>
</p>

More under `docs/assets/`. Runnable script: [`examples/export_sma_sweep_quickstart.py`](examples/export_sma_sweep_quickstart.py).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) · [docs](docs/development/contributing.md).

## Security

Report vulnerabilities privately — see [SECURITY.md](SECURITY.md) (GitHub Security Advisories preferred; do not open public issues for exploitable bugs).

## License

MIT — see [LICENSE](LICENSE).

Public repository: https://github.com/NeoZorK/Monte-Neo
