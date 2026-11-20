# Checks Monte-Neo lacked during the wide search (for stream P)

Not investment advice. Each item: what is needed, why, example.

1. **Family-wise test over many candidates** (White Reality Check / Hansen SPA / Romano-Wolf). `verify_grid` only counts trials for the deflated Sharpe; the Lab had to implement a stationary-bootstrap reality check itself (`scripts/strategy_lab/screen.py`). Needed: `monte-neo verify --family returns_dir/ --benchmark ...` returning p-values (RC, SPA, step-down). Example: 10 promoted candidates' net returns, null = zero.
2. **Cost of the search** (False Strategy Theorem): expected maximum Sharpe of N zero-skill trials for the track length, as a certificate field. The Lab computes it by hand.
3. **Delisting return in portfolio backtests**: a held coin whose data ends keeps its last price (zero P&L) in the Lab's economics; needs a declared terminal return per symbol (survivorship.py prices it only as an estimate for the headline).
4. **Point-in-time liquid universe** as input to `alpha` (top-K by trailing dollar volume known at t) with the membership file derived from it, instead of a static symbol list.
5. **Hash-chained screening ledger for discovery-only runs** with a technical guard that refuses later data (the Lab guards it in code; a first-class `monte-neo screen` mode would make it auditable).
6. **ARL per rebalance phase for `alpha`**: thinning scores to one phase makes the alpha path see no signal on other days (gross falls to 4 %), so the ARL cannot be computed per phase; needs a `--rebalance-phase K/H` option.
7. **Capacity from the stated AUM grid** (250k/500k/5M) in one run, and a gate "capacity >= X".
8. **Funding on perpetual short legs** for the long-short `alpha` economics (real funding history as input).
9. **Delta-neutral carry as a strategy in the full `verify`**: spot long + perpetual short legs with the funding cash flows as explicit P&L. Today only the return-series path exists (`--returns`), which cannot run signal-level checks (ic, placebo, timing, lookahead), so the ARL of any carry is capped at about 1-3 by construction. Needed: `verify --legs` style input with funding per bar, plus lookahead/truncation probes on the entry rule. Example: `r2_carry_basket_v2` (12 coins, trailing funding filter).
10. **Funding on the short legs of cross-sectional long-short portfolios** (see 8): the real funding history per symbol must enter the `alpha` economics and the capacity gate, otherwise the short side is priced too cheaply in bull markets.
11. **Hansen SPA** (superior predictive ability) next to White's Reality Check and Romano-Wolf step-down: the Lab only has White RC (`screen.py reality_check`), which loses power when many candidates are clearly poor.
