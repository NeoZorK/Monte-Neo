<!-- mcp-name: io.github.NeoZorK/monte-neo -->

<h1 align="center">
  <img src="https://raw.githubusercontent.com/NeoZorK/Monte-Neo/main/docs/assets/social-preview.png" alt="Monte-Neo: the independent verifier for trading strategies written by AI agents and humans" width="860"/>
</h1>

<p align="center">
  <strong>The independent verifier for trading strategies written by AI agents and humans.</strong><br/>
  Catch look-ahead bias, hidden trading costs and overfitting before a backtest reaches your money.
</p>

<p align="center">
  <a href="https://pypi.org/project/monte-neo/"><img src="https://img.shields.io/pypi/v/monte-neo?label=PyPI&color=0a7bbb" alt="PyPI version"/></a>
  <a href="https://pepy.tech/projects/monte-neo"><img src="https://static.pepy.tech/badge/monte-neo" alt="Total downloads"/></a>
  <a href="https://pypistats.org/packages/monte-neo"><img src="https://img.shields.io/pypi/dm/monte-neo?label=downloads%2Fmonth" alt="Downloads per month"/></a>
  <a href="https://pypi.org/project/monte-neo/"><img src="https://img.shields.io/pypi/pyversions/monte-neo" alt="Python versions"/></a>
  <a href="https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml"><img src="https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <a href="https://github.com/NeoZorK/Monte-Neo/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license"/></a>
  <br/>
  <a href="https://registry.modelcontextprotocol.io/v0/servers?search=io.github.NeoZorK/monte-neo"><img src="https://img.shields.io/badge/MCP%20Registry-io.github.NeoZorK%2Fmonte--neo-6f42c1" alt="MCP Registry"/></a>
  <a href="https://neozork.github.io/Monte-Neo/guides/agents/"><img src="https://img.shields.io/badge/works%20with-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20Gemini%20CLI%20%C2%B7%20Cursor-444" alt="Works with coding agents"/></a>
  <a href="https://github.com/NeoZorK/Monte-Neo/stargazers"><img src="https://img.shields.io/github/stars/NeoZorK/Monte-Neo?style=flat" alt="GitHub stars"/></a>
</p>

<p align="center">
  <a href="https://neozork.github.io/Monte-Neo/">Docs</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="https://neozork.github.io/Monte-Neo/guides/agents/">Use from agents</a> ·
  <a href="https://neozork.github.io/Monte-Neo/api/verify/">Verifier API</a> ·
  <a href="https://neozork.github.io/Monte-Neo/guides/trap-suite/">Trap Suite</a> ·
  <a href="https://github.com/NeoZorK/Monte-Neo/blob/main/docs/project/CHANGELOG.md">Changelog</a>
</p>

---

## The problem

A coding agent can turn a trading idea into a backtest in minutes. It will then tell you the
strategy returns 40% a year with a Sharpe of 3. Most of the time that number is wrong, for
the same few reasons:

- **Look-ahead bias.** The code reads future bars: `shift(-1)`, centred windows, `bfill`,
  statistics over the whole series, `np.gradient`, an FFT filter.
- **Missing costs.** The edge is smaller than fees and slippage, or it disappears when the fill
  comes one bar later.
- **Selection bias.** The agent tried 300 variants and reports the best one as if it were the only one.

Backtest libraries run whatever code you give them. None of them tell you the backtest itself is broken.

## The solution

**Monte-Neo checks the backtest, not the idea.** Give it the price data and the strategy code
or its positions. It returns one of four verdicts, the checks behind the verdict, concrete next
steps and a reproducible, optionally signed certificate.

<p align="center">
  <img src="https://raw.githubusercontent.com/NeoZorK/Monte-Neo/main/docs/assets/demo-verify.gif" alt="monte-neo verify rejects a leaky agent strategy, the agent fixes it, and the honest verdict follows" width="820"/>
</p>

The agent's strategy used `shift(-1)`, so it knew the next close. Monte-Neo found the leak in four
independent ways and named the line. After the fix, no look-ahead is left, and the verifier tells
the truth: on a random walk, the strategy has no edge after costs.

<details>
<summary>Text output of the first run</summary>

```console
$ monte-neo verify --ohlcv prices.csv --strategy agent_strategy.py --n-trials 40
REJECT  certificate 4f8adb31b088b0c0
  check                    category    status  summary
  data_integrity           integrity   pass    OHLCV is clean
  lookahead_truncation     lookahead   fail    truncation probe: LEAK DETECTED
  lookahead_perturbation   lookahead   fail    future-perturbation probe: LEAK DETECTED
  lookahead_static_lint    lookahead   fail    static lint: negative_shift
  implausible_accuracy     lookahead   fail    next-bar hit rate 1.000
  net_profitability        economics   fail    net total return -64.97% after costs
  deflated_sharpe          statistics  fail    deflated Sharpe 0.000 over 40 trial(s)
  ...                                          (7 more checks)
→ The signal at bar t changes when later bars are removed: compute features only from rows <= t
  (no shift(-k), centered windows, bfill or full-sample stats).
→ Fix the flagged source lines (negative shift, center=True, backward fill) and re-run verify. Lines: 6.
```

The run used a synthetic random walk; output shortened.

</details>

| Verdict | Meaning | CLI exit code |
|---------|---------|---------------|
| `PASS` | No problems found | 0 |
| `PASS_WITH_WARNINGS` | Usable; read the warnings | 0 |
| `NEEDS_MORE_EVIDENCE` | Too few trades, or the Sharpe does not survive the number of variants tried | 1 |
| `REJECT` | The backtest is broken or loses money after costs | 2 |

## What it checks

| Family | Checks |
|--------|--------|
| **Look-ahead** | Truncation probe (does bar *t* change when later bars are removed?), future-perturbation probe, static AST lint (17 rules), implausible hit rate |
| **Economics** | Net return after commission and slippage, break-even cost in bps, one- and two-bar execution delay |
| **Statistics** | Probabilistic and Deflated Sharpe priced by `n_trials`, sample size, holdout consistency, walk-forward out-of-sample check for grid searches |
| **Integrity** | Broken OHLCV, non-deterministic signals |

Every rule is backed by the [Trap Suite](https://neozork.github.io/Monte-Neo/guides/trap-suite/):
25 strategies that are known to lie and 9 honest controls. It runs on every build, so the
verifier cannot silently stop catching a leak or start accusing honest code.

## Where to use it

| You are… | Use Monte-Neo to… |
|----------|-------------------|
| **Building strategies with Claude Code, Codex, Gemini CLI or Cursor** | Make the agent verify its own backtest before it reports results. The MCP server and the Claude Code plugin do this automatically. |
| **Running a strategy repository** | Add the [GitHub Action](#github-action). A pull request whose backtest leaks or loses money after costs fails CI, and the verdict is posted as a PR comment. |
| **A quant, reviewer or allocator** | Check a strategy someone else sends you, with their data and code, in one command. Re-check or verify the signature of the certificate they hand over. |
| **A prop firm, strategy marketplace or trading course** | Screen submissions before a human looks at them. Publish signed certificates next to listed strategies. |
| **A researcher comparing agents** | Run the [Honesty Bench](https://neozork.github.io/Monte-Neo/guides/honesty-bench/): the same tasks for every agent, scored by how often each one claims profit that is not there. |

## Why Monte-Neo

- **Independent.** It checks code it did not write, with probes that do not trust the strategy's own numbers.
- **Built for agents.** An MCP server, a Claude Code plugin with a skill, a slash command and a reminder hook, plus rules for Codex, Gemini CLI and Cursor. Every failed check returns a `next_action` the agent can act on.
- **Reproducible.** The same data, code and `n_trials` always give the same `certificate_id`. Anyone can reproduce a certificate with `--recheck`.
- **Signed.** Ed25519 signatures show who issued a certificate and that nobody edited it.
- **Honest about selection bias.** Declare how many variants you tried, or let `verify_grid` count them for you. The Deflated Sharpe prices them in.
- **Local and private.** Your data and code never leave your machine. MIT licensed.

## Quick start

```bash
pip install monte-neo
```

**Command line**

```bash
monte-neo verify --ohlcv btc_1h.csv --strategy my_strategy.py --n-trials 12 --out verdict.json
```

`my_strategy.py` defines `signal(df)`, which returns one position per bar: `+1` long, `0` flat,
`-1` short. The position decided on bar *t* is filled at the open of bar *t + 1*.

```python
def signal(df):
    fast = df["close"].rolling(20).mean()
    slow = df["close"].rolling(80).mean()
    return (fast > slow).astype(int)
```

**Python**

```python
from monte_neo.verify import verify_strategy

report = verify_strategy("btc_1h.csv", strategy="my_strategy.py", n_trials=12)
print(report["verdict"], report["next_actions"])
```

**Parameter search with honest trial counting**

```bash
monte-neo verify --ohlcv btc_1h.csv --strategy sma.py --grid '{"fast": [10, 20], "slow": [80, 120]}'
```

## Use it from your coding agent

**Claude Code** (plugin with the MCP server, the `verify-strategy` skill and `/verify`):

```text
/plugin marketplace add NeoZorK/Monte-Neo
/plugin install monte-neo@monte-neo
```

**Any MCP client** (Codex, Gemini CLI, Cursor, and others):

```bash
uvx monte-neo mcp
```

It is also listed in the official MCP Registry as `io.github.NeoZorK/monte-neo`. Setup for each
client: [Use from agents](https://neozork.github.io/Monte-Neo/guides/agents/).

MCP tools: `verify_strategy`, `verify_grid`, `probe_lookahead`, `cost_stress`,
`recheck_certificate`, `check_signature`, `verdict_schema`, `verifier_manifest`.

## GitHub Action

```yaml
- uses: NeoZorK/Monte-Neo@v0.27.1
  with:
    ohlcv: data/btc_1h.csv
    strategy: strategies/momentum.py
    n-trials: "12"
    comment: "true"                                        # post the verdict on the pull request
    signing-key: ${{ secrets.MONTE_NEO_SIGNING_KEY }}      # optional: sign the certificate
    upload-certificate: "true"                             # optional: keep it as a workflow artifact
```

The job fails on `REJECT`. The verdict and every check appear in the step summary.

## Certificates you can check

Each run produces a `strategy-verdict/1` JSON certificate. It contains the verdict, every check,
the metrics and the SHA-256 hashes of the data, signals and code.

```bash
monte-neo verify --recheck verdict.json --ohlcv btc_1h.csv --strategy my_strategy.py  # reproduce it
pip install "monte-neo[sign]"
monte-neo verify --keygen issuer                                  # issuer.key + issuer.pub
monte-neo verify --ohlcv btc_1h.csv --strategy my_strategy.py --sign issuer.key --out verdict.json
monte-neo verify --check-signature verdict.json --public-key issuer.pub
```

Show that a strategy passed:

[![Verified by Monte-Neo](https://img.shields.io/badge/verified%20by-Monte--Neo-2ea44f)](https://github.com/NeoZorK/Monte-Neo)

```markdown
[![Verified by Monte-Neo](https://img.shields.io/badge/verified%20by-Monte--Neo-2ea44f)](https://github.com/NeoZorK/Monte-Neo)
```

Link the badge to the signed certificate so that readers can check it themselves.

## Install options

```bash
pip install monte-neo              # verifier, CLI and MCP server
pip install "monte-neo[sign]"      # + Ed25519 certificate signing
pip install "monte-neo[plot]"      # + charts
pip install "monte-neo[apple]"     # + Metal / MLX research engine (Apple Silicon)
pip install "monte-neo[full]"      # everything
```

Python 3.11+ on macOS or Linux.

<details>
<summary><strong>Research engine</strong> (fee-aware bar backtests, sweeps, Monte Carlo)</summary>

Monte-Neo started as a fast local research engine for Apple Silicon, and the verifier runs on it.
The engine is still available. It is in maintenance mode: bug fixes only.

```python
from monte_neo.backtest import ExecutionModel, export_sma_sweep, synthetic_ohlcv

ohlc = synthetic_ohlcv(100_000, seed=42)
model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
out = export_sma_sweep(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], combos=16, model=model, device="auto")
print(out["device"], out["combos"])
```

- Next-bar fills, costs in bps, SL/TP/trailing stops, funding, sessions
- Export API with golden vectors, holdout, walk-forward, CSCV/PBO, Monte Carlo helpers
- Metal / MLX / Numba device selection with a memory planner that falls back to CPU instead of hanging
- Paper OMS for event-level validation

Docs: [quick start](https://neozork.github.io/Monte-Neo/guides/quick-start/) ·
[export API](https://neozork.github.io/Monte-Neo/api/export/) ·
[backtest engine](https://github.com/NeoZorK/Monte-Neo/blob/main/docs/project/backtest_engine.md)

</details>

## Project status

Monte-Neo is in active development (beta). The verifier API and the `strategy-verdict/1`
schema are stable across minor releases. See the
[roadmap](https://github.com/NeoZorK/Monte-Neo/blob/main/docs/project/ROADMAP.md).

**Not investment advice.** Monte-Neo checks backtest methodology. It does not predict future
profit.

## Contributing

Found a way a backtest fooled you or your agent? [Submit it as a trap](https://github.com/NeoZorK/Monte-Neo/issues/new?template=trap_submission.yml).
Bug reports and pull requests are welcome; see the
[contributing guide](https://github.com/NeoZorK/Monte-Neo/blob/main/docs/development/contributing.md).
Report security issues privately: [SECURITY.md](https://github.com/NeoZorK/Monte-Neo/blob/main/SECURITY.md).

## Citation

If Monte-Neo helps your research, please cite it. GitHub shows the citation under
**Cite this repository** ([CITATION.cff](https://github.com/NeoZorK/Monte-Neo/blob/main/CITATION.cff)).

## License

[MIT](https://github.com/NeoZorK/Monte-Neo/blob/main/LICENSE)
