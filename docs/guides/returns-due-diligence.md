# Track record due diligence from returns alone

An allocator often gets a manager's monthly returns and nothing else. Without the code or the positions nobody can prove
there was no look-ahead, and the report says that first. The series still shows the classic red flags.

```bash
monte-neo verify --demo-returns                     # honest, smoothed and too-good track records
monte-neo verify --returns manager.csv --n-strategies 4 --benchmark index.csv --out cert.json
```

The file needs a date column and a return column, in decimals or percent (detected). At least 24 observations are
required. The MCP tool is `verify_returns`.

| Check | Red flag |
|-------|----------|
| `returns_only_scope` | Always shown: what a return series can and cannot prove |
| `return_smoothing` | Lag-1 autocorrelation above 0.2 and significant: illiquid marks or stale prices. Reports the Sharpe after unsmoothing (Getmansky, Lo and Makarov) |
| `zero_kink` | Far fewer small losses than small gains (Bollen and Pool): losses deferred or rounded up |
| `implausible_consistency` | More positive months than the mean and volatility allow; a fail with a monthly Sharpe of 3 or more |
| `round_numbers` | Too many returns on round values for the data's precision |
| `track_record_significance` | Probabilistic and Deflated Sharpe with `--n-strategies` (the best of four funds is not one fund), and the minimum track record length |
| `drawdown_consistency` | A maximum drawdown too shallow for the volatility |
| `benchmark_relation` | Beta, correlation, alpha t-statistic and up and down capture against `--benchmark` |
| `claim_consistency` | With `--claim`: the claimed return, Sharpe or drawdown against the series |

A certificate can be reproduced with `monte-neo verify --returns manager.csv --recheck cert.json`.

Many managers at once: `monte-neo verify --returns-dir managers/ --n-strategies 3 --html managers.html` writes one row
per file, with REJECT and NEEDS_MORE_EVIDENCE first, and exits with 1 when any manager fails.

Honest scope: these are signs, not proof. Arbitrage and lending strategies can be smooth and honest. Read a warning as a
question to ask the manager, not as a verdict on the manager.

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not
predict future returns.
