# Six ways your AI agent's backtest lies, and how to catch each one

*Every number below comes from running the published code (checked on v0.28.0); the strategies are in
[`tests/traps/strategies/`](https://github.com/NeoZorK/Monte-Neo/tree/main/tests/traps/strategies)
and the data is a synthetic random walk (`synthetic_ohlcv(3000, seed=1)`).*

---

Ask a coding agent for "a profitable trading strategy" and you will get one. It will come with
a backtest, a return and a Sharpe ratio. The problem is not that the agent is careless. The
problem is that a backtest is a program that runs on data it can see in full, and there are many
quiet ways for tomorrow to leak into today.

To show this, every example below runs on a **random walk**. By construction, no strategy can
have a real edge on it. Any profit is an artefact, and the only question is how we catch it.

The checker is [Monte-Neo](https://github.com/NeoZorK/Monte-Neo), an open-source verifier:

```bash
pip install monte-neo
monte-neo verify --ohlcv prices.csv --strategy strategy.py --n-trials 1
```

## 1. Reading the next bar: `shift(-1)` and friends

```python
def signal(df):
    return np.sign(df["close"].shift(-1) - df["close"])
```

This is the classic. The position at bar *t* uses the close of bar *t + 1*. Variants include
`diff(-1)`, `pct_change(periods=-3)`, `np.roll(x, -1)` and `.iloc[-1]` (every bar compared with
the last close of the dataset).

**How to catch it.** Run the strategy on the full data, then again on data cut at bar *t*. An
honest signal at bar *t* cannot change when later bars are removed. This *truncation probe* does
not care how the leak is written. On this strategy Monte-Neo reports `REJECT`, with four
independent look-ahead failures: the truncation probe, the perturbation probe, the static lint
(`negative_shift`, with the line number) and a next-bar hit rate of exactly 1.000.

## 2. Statistics over the whole series

```python
def signal(df):
    close = df["close"]
    z = (close - close.mean()) / close.std()
    return np.where(z < 0.0, 1, 0)
```

Nothing is shifted, yet the mean and standard deviation include every future bar. The same
happens with `rank(pct=True)`, `pd.qcut`, `np.percentile`, `idxmax()`, or fitting a scaler on
the full dataset.

**How to catch it.** Rewrite the future (mirror the returns after bar *t*) and check that the
signals before *t* stay exactly the same. This *future-perturbation probe* catches every
whole-sample statistic, including ones hidden inside helper functions.

## 3. Signal processing that looks both ways

```python
slope = np.gradient(close)                                  # central difference: uses t + 1
smooth = np.convolve(close, np.ones(9) / 9, mode="same")    # centred kernel
```

`np.gradient` uses central differences. `mode="same"` centres the kernel on each bar.
`filtfilt` and `savgol_filter` are zero-phase or centred by design, and an FFT low-pass mixes
every bar with every other. These are the leaks experienced engineers write, because they are
correct in signal processing and wrong in trading.

**How to catch it.** Both dynamic probes flag all of them. Since v0.24.0 the static lint names
them too (`central_difference`, `centered_filter`, `full_sample_transform`), so the agent is told
which line to fix.

## 4. Costs that are not there

```python
def signal(df):
    return np.where(df["close"].diff() < 0.0, 1, 0)   # buy every down-tick
```

This code is honest: no look-ahead at all. It trades almost every bar. With 5 bps commission
and 5 bps slippage per side, Monte-Neo measures a net return of **−77%** and a break-even cost of
**0.10 bps**. Any real venue charges more than that.

**How to catch it.** Always report the net return after costs, and the break-even cost, which
says how much room the edge has.

## 5. Perfect fills

A strategy that decides on the close of bar *t* cannot also trade at that close. Monte-Neo fills
at the open of bar *t + 1*, then re-runs the backtest with one and two bars of extra delay. An
edge that exists only with instant fills is timing, not signal.

## 6. The best of many tries

Generate 200 random long/flat strategies on the random walk and keep the best one. Its backtest
looks good: a **+3.66%** return and a very high annualized Sharpe on minute bars. Verify it
without saying how it was found, and the Deflated Sharpe is **0.876**: `PASS_WITH_WARNINGS`.

Now declare the truth, `--n-trials 200`. The Deflated Sharpe drops to **0.054** and the verdict
becomes `NEEDS_MORE_EVIDENCE`. The strategy did not change. Only the honesty of the report did.

**How to catch it.** Ask for `n_trials`, or run the search inside the verifier
(`monte-neo verify --grid …`) so that it counts the variants itself and adds a walk-forward check.

## Put it in the loop

Catching these once is not enough. The checks need to run every time an agent claims a result:

- **In the agent:** the MCP server (`uvx monte-neo mcp`) or the Claude Code plugin. Each failed
  check returns a `next_action`, so the agent can fix the code and try again.
- **In CI:** a GitHub Action that fails the pull request on `REJECT` and posts the verdict.
- **For others:** a reproducible `strategy-verdict/1` certificate. Anyone can re-run it, you can
  sign it with Ed25519, and readers can check the signature on the
  [verification page](https://neozork.github.io/Monte-Neo/verify/).

These patterns and many more are in the open
[Trap Suite](https://neozork.github.io/Monte-Neo/guides/trap-suite/). If your agent found a way
to fool you that is not there yet,
[send it as a trap](https://github.com/NeoZorK/Monte-Neo/issues/new?template=trap_submission.yml).

*Monte-Neo checks backtest methodology, not future profit. Not investment advice.*
