# Hall of Fame

> Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

The Hall of Fame lists strategies by the **evidence** in their Monte-Neo certificate. It shows the author, the strategy name, the dates and the
certificate SHA-256, and **never the strategy itself**. The live tables are on [the Hall of Fame page](../hall-of-fame.md) and in the README.

The rules are one machine-readable file, `src/monte_neo/hall/hall_rules_v1.json` (`hall-of-fame/1`, provisional). The blocks below are
generated from it (`monte-neo hall build` refreshes them) and a test fails when this page and the file disagree.

## How the score works

<!-- hall:score:start -->
1. ARL level (higher first)
2. ARL depth (higher first)
3. Deflated Sharpe on the certificate (higher first; no value ranks last)
4. certificate date (earlier first)
5. entry id (alphabetical)

Return, profit and Sharpe are not part of the score. The Deflated Sharpe only breaks ties between equal ARL and depth, and it already pays for the n_trials recorded in the certificate. Verdicts never ranked: `REJECT`.
<!-- hall:score:end -->

## Trust tiers

<!-- hall:tiers:start -->
| Tier | Name | Ranked | Meaning |
|---|---|---|---|
| A | open | yes | The code is public, so anyone can run `monte-neo verify --recheck` and reproduce the certificate. The submitter reproduced it locally and the maintainer reproduces it again before the entry is merged. |
| B | privately verified | yes | The author passed the code to the maintainer privately. The maintainer reproduced the certificate and signed the entry; the code is not published. The signature must verify against a key in `hall_of_fame/maintainer_keys.json`. |
| C | self-reported | no | Only the author's certificate. It is never reproduced by anyone else, never ranked and never gets a medal; it is listed separately. |
<!-- hall:tiers:end -->

## Limits, categories, medals

<!-- hall:limits:start -->
- Table size: top 10 overall and in each category; ranked under `hall-of-fame/1` with ARL rules `arl-rules/1`.
- Categories: `trend`, `mean-reversion`, `carry`, `pairs`, `cross-sectional`, `seasonality`, `other`.
- Medals (gold = rank 1, silver = rank 2, bronze = rank 3) are given per table: overall and per category.
- At most 3 entries per author per month; `n_trials` of at least 1 is required.
- Two entries with the same data hash and signal hash, or the same data hash and strategy source hash, are the same strategy under different names: only the earliest entry (by submission date, then id) stays ranked.
<!-- hall:limits:end -->

## Honest rules

<!-- hall:honesty:start -->
1. The score is evidence, not return: the order is ARL, depth, then the Deflated Sharpe, then the certificate date. A REJECT verdict is never ranked.
2. n_trials is mandatory: a certificate without it is refused, and its Deflated Sharpe already pays for every variant the author tried.
3. Only tier A (open) and tier B (privately verified and signed by the maintainer) entries are ranked. Self-reported (tier C) entries are shown apart and never get a medal.
4. Every entry carries the SHA-256 of its certificate; a changed certificate, a bad certificate signature or a bad maintainer signature fails the build.
5. The same strategy under another name is one entry (same data and signal hashes), and an author can add at most 3 entries per month.
6. Medals and holding periods come from monthly snapshots in hall_of_fame/history.jsonl, never from a hand edit.
7. A change of these rules or of the ARL rules is a new version and a new table; the old table is archived, never rewritten.
8. These tables rate the evidence about a strategy. They are not investment advice, not a recommendation to trade and say nothing about future returns.
<!-- hall:honesty:end -->

## How to join

1. Verify your strategy with `monte-neo verify ... --n-trials N` (N = every variant you tried) and keep the certificate.
2. Prepare the entry, offline:

   ```bash
   monte-neo hall submit cert.json --author "Your Name" --name "My strategy" --category trend --tier A \
     --code-url https://github.com/you/repo --ohlcv data.parquet --strategy-file strategy.py
   ```

   Tier A runs the recheck locally and refuses an entry that does not reproduce, a `REJECT` verdict, a duplicate of an existing entry
   or an author over the monthly limit. Tier B (`--tier B`) needs no code from you here: send the code and data privately to the maintainer,
   who runs `monte-neo hall attest` (it reproduces the certificate and signs the entry). Tier C is only listed, never ranked.
3. Open a pull request that adds `entries/<id>.json` and `certificates/<id>.json` under `hall_of_fame/`. The maintainer reproduces the
   certificate before merging and runs `monte-neo hall build`, which rewrites the tables, the badges and the history.

`monte-neo hall build --check` fails when a generated file is out of date, and `build` refuses to write while any entry has a changed
certificate (SHA-256), a bad certificate signature, a missing `n_trials`, or a missing or untrusted maintainer signature (tier B).

## Medals and holding periods

Ranks 1, 2 and 3 of each table get a gold, silver or bronze SVG badge in `hall_of_fame/badges/` with the certificate SHA-256 in it; the
generated page lists the Markdown snippet to paste into your README. "Holds this rank" is computed from the monthly snapshots in
`hall_of_fame/history.jsonl` (months with a recorded snapshot), never edited by hand.

## Seed entries

The first entries are Strategy Lab examples (shown as "Strategy Lab example"), validation period only,
holdout untouched, ARL 3-4 under the **provisional** `arl-rules/1`. Their data and code are not in this repository, so they are tier B. They are signed
with a seed key listed in `hall_of_fame/maintainer_keys.json`; the maintainer replaces it with their own key and re-attests.
`hall_of_fame/display.json` (unsigned) changes only what the tables and badges show as the author of listed entries; the signed
entry keeps its own author field.
