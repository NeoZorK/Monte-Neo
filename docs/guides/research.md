# Honest strategy search (`monte-neo research`)

`monte-neo verify` checks one strategy. Most backtest self-deception happens one step earlier: you try many variants, keep the best and
then verify only the winner. `monte-neo research` runs the **search itself** as a pipeline whose rules make that hard to do by accident,
survives a crash or a power cut, and ends with a report that says what the search could and could not show. Not investment advice; a
result here rates the evidence, not the strategy.

## The rules the tool enforces

| Rule | How |
|------|-----|
| The split is fixed first | `init` writes the discovery / validation / holdout dates, the bar count of each part and the data hash into a hash-chained record before any candidate runs. A split is fixed once per project. |
| Validation and holdout are closed while you screen | `screen` hands the strategy code a table that ends at the discovery cut; the later rows are not in memory. |
| Every variant is counted | Each screened variant (code hash and parameters) is a ledger entry, also the ones that failed or lost. A renamed copy or a changed docstring is not a new variant. |
| Pre-registration | `promote` writes the batch and its hash (`batches/batchNNN.json` and the record) **before** validation is read. `validate` refuses a batch whose file was edited or removed, and a candidate whose stored code or parameters changed. |
| Validation is read once per batch | A second read is refused, and the refusal is written into the record, where the report shows it. |
| `n_trials` is automatic | The number of promoted candidates of all batches; it only grows. Screened variants are reported beside it. |
| The family is tested, not the winner | SPA (Hansen), the White Reality Check and the Romano-Wolf stepdown over **all** validated candidates; a significant loser is never an edge. |
| The search has a price | The Sharpe that luck alone delivers for this many candidates on this many bars (False Strategy Theorem), and the smallest Sharpe the search could detect at all. |
| One holdout, one opening | `holdout` freezes one candidate (hash of code and parameters) and opens it once. A second opening is written down and **permanently sets D4 of the ARL depth to 0** (`arl-rules/2`). |

`holdout` refuses a candidate whose validation gate is closed (not significant after Romano-Wolf, or a Sharpe below the luck level);
`--override` opens it anyway and the override is shown in the report. Both `holdout` and `freeze` need `--confirm`: neither can be undone.

## Walkthrough on the built-in demo data

```bash
monte-neo research init --dry-run --project demo-research
```

runs the whole pipeline on a synthetic, driftless random walk (ten years of daily bars) and prints the funnel, the search statistics and
the diagnosis. A correct run finds nothing: no candidate passes the gate, and the report says why. Open `demo-research/report.html`. The same
steps by hand, on your own data:

```bash
# 1. the split and the project (data hash, policy, profile, grammar hash go into manifest.json)
monte-neo research init --project r1 --data prices.csv --discovery-end 2021-01-01 --validation-end 2024-01-01 \
    --grammar grammar.py --profile trend_cta

# 2. every variant of the grammar on discovery only; run the same command again after any interruption
monte-neo research screen --project r1

# 3. pre-register the batch, then read validation once
monte-neo research promote --project r1 --top 5
monte-neo research validate --project r1

# 4. the report: funnel, search statistics, candidates, anti-patterns, diagnosis, next actions
monte-neo research report --project r1 --certify-top 3

# 5. only for a candidate whose gate is open: freeze it and open the holdout once, then certify and hand over
monte-neo research holdout --project r1 --candidate ID --confirm
monte-neo research certify --project r1
monte-neo research handoff --project r1 --dossier out/dossier --hall out/hall --author "Name" --name "my rule" --category trend

# 6. keep recording the frozen rule on new data (the hash-chained forward journal)
monte-neo research forward freeze --project r1 --data prices.csv
monte-neo research forward record --project r1 --data prices_newer.csv
```

`--data` is needed once; later steps read the path from the manifest. `status` shows the stage, counts, the progress of a running step with its
ETA, whether a command holds the project, the anti-pattern warnings and the next step. `report --certify-top K` certifies the best K validated
candidates so that each gets an ARL with its depth (`arl-rules/2`) and, with `--profile`, the coverage block of its strategy profile.

### The grammar plugin

A grammar file says which variants to screen; it runs with your permissions, so use only your own files:

```python
SOURCE = """
import numpy as np
def signal(df, n=20, side=1):
    ...                       # positions per bar, no look-ahead
"""                           # or STRATEGY = "strategy.py" next to the grammar file
GRID = {"n": [10, 20, 40, 80], "side": [1, -1]}      # or: def variants(): yield {"n": 10}
LABEL = "ma"
```

At most 5000 variants: every one is a trial the search pays for. The grammar file is hashed into the manifest; changing it after `init` is a
different search and is refused. `monte-neo research screen --strategy file.py --grid '{"n": [10, 20]}'` does the same without a grammar file.

### Interruptions

The record is hash-chained and every write is atomic. After a crash, a power cut, a closed terminal or `--max-seconds`, run the same command again: variants already in
the ledger are skipped. A line cut in half by a power failure is dropped when the project opens (written to `healed.log`). A lock file with the process id keeps two
commands from writing at once; a lock whose process is gone is taken over. `status` recomputes progress from the record, not from the manifest.

## What the report tells you

`research report` writes `report.json` (schema `research-report/1`) and `report.html` (the funnel as bars, the candidates, the diagnosis).

* **Funnel.** Variants tried, ran, positive on discovery, promoted, validated, positive on validation, above the luck level, significant after Romano-Wolf,
  family SPA, frozen, holdout opened once, ARL. Publish it for the losers as well as the winners.
* **Cost of the search.** The expected best Sharpe of luck for the promoted candidates, the SPA and Reality Check p-values.
* **False discoveries.** Benjamini-Hochberg and Storey q-values of every validated candidate at the policy level `fdr_q`.
* **Independent tries.** Candidates whose returns correlate at `|rho| >= 0.95` are joined (a 20-day and a 21-day average are one idea); the larger of the
  cluster count and the participation ratio of the correlation eigenvalues is the effective number of tries, so the estimate can only make the search look
  *more* expensive. The ARL still pays for the raw count.
* **Power.** The smallest annual Sharpe this search could detect on this sample with this many tries (family level 5 %, power 80 %). If it is far above any plausible Sharpe, the search is pointless before it is run.
* **Anti-patterns.** Reading validation again, several batches on one window (the number of tries grows and no new data came in), repeated refused steps, an overridden gate, a spoiled holdout, a search that cannot detect anything.
* **Diagnosis.** Why it did not pass, in groups of causes: implementation defects, the search explaining the result, too few independent observations, costs, market exposure instead of alpha,
  one regime, capacity, survivorship. The **next actions add information** (a later window, another market, measured costs, the forward record), never another variant: more variants on the same data
  spend the same sample again and raise the price of the search.
* **Hand-off.** The frozen champion goes to `dossier` (`handoff --dossier`, or `dossier --research PROJECT` for the funnel) and to a Hall of Fame entry (`handoff --hall`, tier C unless you attest it).

Python and MCP use the same steps: `monte_neo.research.ResearchProject` and the MCP tool `research_search(project, action, ...)`.

## Limits, said plainly

* It cannot detect a split chosen after peeking at the data: the record proves only the order of events inside it.
* It counts the variants it is shown: variants tried outside the project are invisible to it. The record and the lock protect against honest mistakes and over-eager agents, not against a process that may rewrite the disk (run the search where the agent cannot write the project folder).
* The effective number of tries and the minimum detectable Sharpe are approximations (a normal approximation of the Sharpe, Bonferroni over the tries); they are meant to be read as orders of magnitude.
* The forward journal records what the rule *would have done* on data that arrived after it was frozen. It places no orders and uses no account, applies no costs, and a bar recorded days late is flagged.
* Survivorship and look-ahead of the data itself are checked by `verify`, not here. A passing gate is evidence about the search, not a recommendation to trade.

## A family of candidates tried elsewhere

`monte-neo research family --returns DIR` (a folder of `date,return` files, one per candidate, or one wide table) runs the family
tests without a project: White Reality Check, Hansen SPA, Romano-Wolf and the Sharpe luck delivers for that many candidates.
It cannot know how many variants you screened before, so use a project when you can.

## The funnel report

`research funnel` (and `funnel(project)`) prints how many variants were tried, how many ran, how many were positive on
discovery, how many were promoted, and how many survived each validation gate (positive Sharpe, above the luck level,
significant after Romano-Wolf, family SPA), then the freeze, the holdout state and the ARL headline once `certify` has run.
Publish it for the losers as well as the winners: a result without its funnel cannot be priced.

The certificate gets two extra rows, `search_cost` and `family_spa`, and is computed with the project's `n_trials`
(Deflated Sharpe and the ARL levels 4-6 therefore pay for the whole search). The ARL then reads the sealed holdout evidence:
D4 counts only for a holdout that was frozen and opened exactly once.

## Cross-sectional portfolios: breadth

Many names are not many independent bets: when one market factor drives them, thirty coins may be three bets.
`monte-neo research breadth --signal signal.csv --forward-returns fwd.csv` (tables with dates down and names across) and
`monte_neo.research.breadth_report` report the information coefficient per date, the **effective number of independent
bets** (participation ratio of the correlation eigenvalues, never above the number of names) and a significance that is the
smaller of the Newey-West t of the IC series and `IC x sqrt(effective breadth x dates)`. The naive figure that treats every
name as independent is printed next to it, with the inflation factor. The check row `breadth_significance` warns when a result
is significant only under that naive reading.

## What this does not do

It does not find alpha for you and does not make a holdout reusable. It cannot detect a split chosen after peeking at the
data (the record only proves the order of events inside it), and it counts variants it is shown: variants tried outside the
project are invisible to it. Survivorship and look-ahead are checked by `verify`, not here.

## Checks added for wide searches

These came out of running a wide search on perpetual futures and are useful beyond it.

| Need | How |
|------|-----|
| Carry with explicit funding | See the [carry guide](carry.md): `monte-neo verify --carry table.csv --strategy rule.py --carry-costs 10,5`. The table has `timestamp, spot_close, perp_close` and `funding_rate` (fraction a long pays per bar, settled over that bar) or `funding_bps`. The hedged pair (spot long, perpetual short) becomes an instrument whose return is `spot return - perpetual return + funding`; `signal(df)` returns 1 (hold) or 0 (flat) and meets the look-ahead, truncation, cost and significance checks. Entry and exit pay both legs. The row `carry_decomposition` says whether the profit is funding or the basis moving. MCP: `verify_carry`. |
| Funding on short legs of a long-short portfolio | `monte-neo alpha --funding funding.csv` (`timestamp, symbol, funding_bps` a long pays per bar). The row `funding_drag` prices every leg with its real funding, short legs reported apart, and warns when the history covers less than 80 % of the held positions. |
| Capacity on a stated AUM grid | `monte-neo alpha --aum-grid 250000,500000,5000000 --min-capacity 500000`: net Sharpe at each AUM after impact, commission and funding, and a gate (`capacity_grid`). |
| Point-in-time liquid universe | `monte-neo alpha --liquid-top 30 --liquid-lookback 30`: only the K symbols with the highest traded value over the bars before each date can be held; the membership windows are derived and checked for look-ahead. |
| Delisting | `monte-neo alpha --terminal-returns delisted.csv` (`symbol, return`): the return on the bar after the last price. Symbols whose data ends early without a declared return are flagged (`delisting_returns`). |
| One rebalance phase | `monte-neo alpha --rebalance-phase 2/5`: rebalance on bar 2 of every 5 and hold the scores in between; run it for every phase and report the worst. |
| Family test without a project | `monte-neo research family --returns DIR`. |

Each option is recorded in the report settings, so `recheck` reproduces the certificate.
