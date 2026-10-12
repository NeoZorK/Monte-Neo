# Your thresholds, your experiment history, your model's training date

Three options of `monte-neo verify` (and of the MCP tool `verify_strategy`) bring an institution's own context into a
certificate.

## `--policy`: your thresholds as code

The verifier's defaults are a floor. A fund, a bank's model-validation team or a prop desk has its own rules. Write
them once:

```bash
monte-neo policy init                 # writes a commented policy.toml
monte-neo policy show policy.toml      # validates it and prints the hash certificates will record
monte-neo verify --ohlcv data.csv --strategy s.py --policy policy.toml
```

```toml
[policy]
name = "model-risk-strict"
version = "2026-10"
on_breach = "reject"          # or "needs_more_evidence"

[inputs]                      # applied before the run
min_trades = 100
cost_multiplier = 2.0         # commission and slippage times two

[rules]                       # applied to the result
allow_warnings = false
min_deflated_sharpe = 0.95
min_sharpe = 0.5
max_drawdown = 0.25
required_checks = ["lookahead_truncation", "net_profitability"]
fail_on_warn = ["implausible_performance"]
```

The `policy` check row lists every breached rule. The whole policy goes into the certificate's
`reproducibility.policy` with its sha256 hash, so `--recheck` applies the same rules and a reader knows which rules the
result was judged by. The same strategy can pass one policy and fail another, and the reason is visible in both reports.

## `--trials-from`: count what your tracker already logged

The Deflated Sharpe needs the number of variants tried. If your runs are in an experiment tracker, count them from disk.
Nothing goes over the network, and no keys are needed.

| Spec | Reads |
|------|-------|
| `mlflow:./mlruns[:EXPERIMENT]` | The MLflow file store; deleted runs count, because they were tried |
| `mlflow:sqlite:///mlflow.db[:EXPERIMENT]` | An MLflow SQLite tracking database, opened read-only |
| `optuna:sqlite:///study.db[:STUDY]` | An Optuna study, opened read-only; pruned and failed trials count |
| `wandb:runs.csv` | A W&B runs table exported as CSV |
| `raytune:~/ray_results/EXPERIMENT` | A Ray Tune experiment folder (trial folders and the experiment state) |
| `csv:trials.csv` | One row per trial |
| `ledger:PATH` | A Monte-Neo ledger |

The largest of `--n-trials`, the ledger count and the imported count is used. The `trials_imported` row says where the
number came from.

## Team ledger

`--ledger PATH` now works for a team on a shared drive. Writes are locked, so two people verifying at once keep the
hash chain intact, and every entry records who wrote it and from which host. Point everyone at the same file to count
the variants the whole team tried on the same data.

## `--model-cutoff`: did a language model trade a past it remembered?

A strategy that asks a language model (or a pre-trained time-series model) about dates inside its training data can
"predict" news and prices it has already read. No code probe sees this, because the leak is in the model's weights.

```bash
monte-neo verify --ohlcv data.csv --strategy llm_signal.py --model-cutoff 2024-06
```

The `model_cutoff` check compares the Sharpe before and after that date with a block bootstrap, next to buy-and-hold on
the same dates:

- `fail` (look-ahead): the edge is significant before the cutoff and gone after it.
- `warn`: most of the edge sits in the period the model was trained on.
- `skip`: fewer than 30 bars on one side.

A market that changed at the same time can also cause a drop, so read the buy-and-hold numbers in the details. The
only clean test is a period that starts after the cutoff.

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not
predict future returns.
