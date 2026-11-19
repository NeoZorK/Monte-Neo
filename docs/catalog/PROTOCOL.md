# Protocol for mass verification of the catalog

> Not investment advice. The goal is an honest map of which popular strategies survive independent verification, and why the others do not.

## 1. Principle

Running 100 strategies and publishing the best ones is a multiple-testing exercise. The protocol is built so that the ranking cannot be inflated by choosing among the 100, and so that the losers are published with the same prominence as the winners.

## 2. Pre-registration (before any run)

Frozen and hashed (SHA-256) in a file committed before the first result exists:

- the catalog version (`strategies.yaml` hash): ids, formulas, parameters;
- data sources, symbols, date ranges and the three-way split (section 4);
- the cost model per asset class and its stress multiples (section 5);
- the Monte-Neo version and the list of checks and gates;
- the ranking rule and the classification rule (section 7);
- `n_trials` (section 3).

Any change after the first result is a new protocol version: the old results stay published, and `n_trials` for the new version includes every variant already run.

## 3. Trial count

`n_trials = 100` for the Deflated Sharpe Ratio of every catalog strategy (Bailey and Lopez de Prado 2014), plus any variants added later. This penalizes every strategy for the existence of the other 99. That is intentional and is not reduced for correlated strategies.

As a secondary, clearly labelled statistic only, the report may add an effective trial count from clustering the strategy return matrix (Lopez de Prado). The headline verdict uses 100.

Probability of backtest overfitting (CSCV, Bailey et al. 2017) is computed on the matrix of all 100 return streams and reported for the catalog as a whole.

## 4. Split: discovery / validation / sealed holdout

| Window | Purpose | Rule |
|---|---|---|
| Discovery | Debug the implementation against published figures; sanity checks | Parameters are frozen, so nothing is fitted here. Results from this window are never used to rank. |
| Validation | The ranking window; all gates run here | Evaluated once per protocol version. |
| Sealed holdout | Final test of the shortlist | The data file hash is recorded; it is opened once for the pre-declared shortlist (e.g. the strategies whose validation evidence level reaches the pre-declared bar), never to choose among variants. |

Default calendar (to be fixed by the owner before the first run): crypto daily from the first full-year of listing to 2020-12-31 discovery, 2021-01-01 to 2024-12-31 validation, 2025-01-01 onward sealed. Equity/ETF/allocation series use the longest open history: discovery to 2009-12-31, validation 2010-01-01 to 2022-12-31, holdout 2023-01-01 onward. A single regime must not dominate validation; the regime-split check (section 6) reports performance by regime even though validation is a single window.

## 5. One cost model for everyone

- One cost schedule per asset class (commission, spread/slippage, borrow, funding), written into the pre-registration, with the base case and 2x and 4x stress.
- A strategy is judged on the base case; the cost-stress multiples are reported and used by the cost-margin gate.
- Cost parameters are taken from published fee schedules on the run date (recorded), not from the author's optimistic estimates. The earlier Lab finding that realistic spread was far above the model's assumption is the reason this is mandatory.

## 6. What is run on every strategy

1. Data integrity and look-ahead probes (existing checks).
2. Per-type profile checks from [TYPES.md](TYPES.md) (see the implementation plan for status; checks not yet implemented are listed as "not run" and the strategy cannot reach the top evidence levels without them).
3. Benchmark-relative evaluation: alpha after beta to the matching buy-and-hold, not raw Sharpe.
4. DSR with `n_trials = 100`, PBO on the catalog matrix, timing/significance test.
5. Regime split and sub-period stability.

## 7. Classification and ranking

Each strategy gets, from the verifier, a verdict and an evidence level (existing scale). The rank is by evidence level, then by DSR, then by alpha after beta; ties are shown as ties. The catalog is also classified by type, because comparing a short-vol strategy with a trend strategy on one Sharpe axis is misleading. Result classes, fixed in advance:

- **Cannot be tested here** (needs data or a venue we do not have): listed, not scored.
- **Rejected** (a hard gate failed, e.g. look-ahead, no edge after costs, alpha not distinguishable from beta).
- **Needs more evidence** (passes gates but fails significance, DSR or trade count).
- **Passes with warnings / passes** at the pre-declared level; only then is the holdout opened.

Multiple-testing control across the 100 uses Holm or Benjamini-Hochberg on the timing/significance p-values, stated in the pre-registration.

## 8. How the ranking avoids self-deception

- **Frozen canonical parameters:** no optimization, so the best-of-many selection effect is limited to the choice of 100 strategies, which `n_trials` penalizes.
- **Unfavourable results are published first-class:** the full table is released with every strategy, including rejected and untestable ones, sorted by id as well as by rank. A "casualties" section lists every strategy that failed and the specific gate that stopped it. Failure reasons are the educational content.
- **Negative controls in the same run:** random entry, always flat, martingale and grid. If a control reaches a pass level, the verifier is miscalibrated and the run is withdrawn; the false-positive rate is published.
- **Holdout opened once;** its hash and opening time are published. A strategy that passes validation and fails holdout is published as such.
- **No post-hoc edits:** corrected bugs produce a new protocol version with the old results retained.
- **Benchmark honesty:** every strategy is shown next to buy-and-hold of its own asset over the same dates. In a strong bull window most long-biased strategies underperform that line; this is shown.
- **Reproducibility:** pinned versions, data file hashes, one command to rerun, certificates for every verdict.
- **Language:** results are described as "survived/failed verification on these data". No statement of guaranteed or expected profit; the disclaimer is on every page and image.

## 9. Output

`results.csv` (one row per strategy: id, type, verdict, evidence level, DSR, alpha after beta, net Sharpe, max drawdown, trades, failed gates), per-type tables, the casualties list, the control-calibration table, and the pre-registration hash. This feeds the README, the Hall of Fame and any public post.

## 10. Limits

- A pass means "no evidence of error found and a statistical edge in this sample", not future profit.
- Daily bars cannot verify intraday execution; tier C is out of scope for the first run.
- Results depend on data sources; each is recorded with its licence and hash.
