# Monte-Neo

<p class="mn-hero-logo" markdown="1">
![Monte-Neo](assets/logo-sphere.png){ width="120" }
</p>

<p class="mn-tagline" markdown="1">
**The independent verifier for trading strategies written by AI agents and humans**  
Catch look-ahead bias, hidden trading costs and overfitting before a backtest reaches your money
</p>

<p class="mn-badges" markdown="1">
[![PyPI](https://img.shields.io/pypi/v/monte-neo?label=PyPI&color=0a7bbb)](https://pypi.org/project/monte-neo/)
[![Downloads](https://static.pepy.tech/badge/monte-neo)](https://pepy.tech/projects/monte-neo)
[![Downloads/month](https://img.shields.io/pypi/dm/monte-neo?label=downloads%2Fmonth)](https://pypistats.org/packages/monte-neo)
[![CI](https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml/badge.svg)](https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-io.github.NeoZorK%2Fmonte--neo-6f42c1)](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.NeoZorK/monte-neo)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/NeoZorK/Monte-Neo/blob/main/LICENSE)
</p>

!!! tip "Install"
    ```bash
    pip install monte-neo
    monte-neo verify --ohlcv prices.csv --strategy my_strategy.py --n-trials 12
    ```

## The problem

A coding agent can turn a trading idea into a backtest in minutes, and then report a Sharpe
of 3. Most of the time that number is wrong:

- **Look-ahead bias:** the code reads future bars (`shift(-1)`, centred windows, `bfill`,
  whole-series statistics, `np.gradient`, FFT filters).
- **Missing costs:** the edge is smaller than fees and slippage, or needs a perfect fill.
- **Selection bias:** the best of 300 variants is reported as if it were the only one.

## What Monte-Neo does

It checks the backtest, not the idea. Give it the price data and the strategy code or its
positions. It returns `PASS`, `PASS_WITH_WARNINGS`, `NEEDS_MORE_EVIDENCE` or `REJECT`, the
checks behind the verdict, concrete next steps for the agent, and a reproducible `strategy-verdict/1`
certificate that can be signed.

| Family | Checks |
|--------|--------|
| **Look-ahead** | Truncation and future-perturbation probes, static AST lint (20 rules), implausible hit rate |
| **Economics** | Net return after costs, break-even cost in bps, one- and two-bar execution delay |
| **Statistics** | Probabilistic and Deflated Sharpe priced by `n_trials`, sample size, holdout, walk-forward for grids |
| **Integrity** | Broken OHLCV, non-deterministic signals |

## Where to use it

- **Inside your coding agent:** Claude Code plugin, or the MCP server for Codex, Gemini CLI and
  Cursor. See [Use from agents](guides/agents.md).
- **In CI:** a GitHub Action that fails the pull request on `REJECT` and posts the verdict.
- **When reviewing someone else's strategy:** re-check their certificate and verify its signature.
- **When screening submissions** at a prop firm, marketplace or course.
- **When comparing agents:** the [Honesty Bench](guides/honesty-bench.md).

## Learn more

- [Verifier API](api/verify.md): checks, verdicts, certificates, re-checks and signatures
- [Trap Suite](guides/trap-suite.md): 40 strategies that lie and 15 honest controls, and how to add yours
- [Honesty Bench](guides/honesty-bench.md): score how honestly agents report backtests
- [Verify a certificate](verify.md): check a signed certificate in your browser
- [Six ways your agent's backtest lies](marketing/article-six-ways.md): the traps, with numbers
- [FAQ](guides/FAQ.md) · [Changelog](project/CHANGELOG.md) · [Roadmap](project/ROADMAP.md)

## Research engine (maintenance mode)

Monte-Neo started as a fast local research engine for Apple Silicon: fee-aware next-bar
backtests, parameter sweeps with golden vectors, Monte Carlo helpers and a paper OMS, with
Metal / MLX / Numba device selection. The verifier runs on this engine. The engine still works
and receives bug fixes, but new work goes into the verifier.

```python
from monte_neo.backtest import ExecutionModel, export_sma_sweep, synthetic_ohlcv

ohlc = synthetic_ohlcv(100_000, seed=42)
model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
out = export_sma_sweep(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], combos=16, model=model, device="auto")
print(out["device"], out["combos"])
```

See the [quick start](guides/quick-start.md) and the [export API](api/export.md).

<div class="mn-gallery" markdown="1">

![SMA sweep demo](assets/demo_sma_sweep.png){ loading=lazy }

![Memory plan demo](assets/demo_memory_plan.png){ loading=lazy }

</div>

Source: [github.com/NeoZorK/Monte-Neo](https://github.com/NeoZorK/Monte-Neo) · MIT license ·
Not investment advice.
