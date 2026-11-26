# Monte-Neo strategy catalog

> **Not investment advice.** This catalog is research and education material. Nothing here is a recommendation to buy or sell anything, and no result, past or hypothetical, guarantees future performance. Many strategies listed are expected to fail verification; that is part of the point.

The catalog has four parts:

| File | Content |
|---|---|
| [TYPES.md](TYPES.md) | 24 strategy and benchmark types (passive, 60/40, risk parity, factors, trend/CTA, mean reversion, stat-arb, carry, short vol, merger arb, macro, ...): how each is measured, its typical traps, which Monte-Neo checks apply, what data it needs, and what Monte-Neo cannot verify |
| [INDEX.md](INDEX.md), [strategies.yaml](strategies.yaml), [cards/](cards/) | 100 popular strategies with canonical, frozen parameters from the source, and one card per strategy |
| [strategies_mn.yaml](strategies_mn.yaml) | Extension MN-1: 10 market-neutral and arbitrage strategies (structure and a worst scenario per entry), verified with `n_trials` = 100 + the extension size |
| [strategies_x2.yaml](strategies_x2.yaml) | Extension X-2: 20 strategies for subcategories left empty (market making, order flow, machine learning, long volatility, portfolio construction, overlays, crypto events) and failing controls (copy trading, martingale, averaging down) |
| [PROTOCOL.md](PROTOCOL.md) | The honest protocol for verifying all 100 at once (pre-registration, `n_trials` = catalog size, sealed holdout, how failures are published) |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Historical design plan for type-aware verification profiles. The shipped feature is `monte-neo verify --profile ID` ([profiles guide](../guides/profiles.md)); the `monte-neo catalog` command in the plan does not exist |

Data tiers: **A** = daily OHLCV from open data (62 strategies), **B** = needs other data such as fundamentals, option chains, futures curves or macro releases (37), **C** = intraday/tick/order book (1). Tier A is implemented first.

## Rules of this catalog

1. **Canonical parameters only.** Each strategy uses the parameters printed in its source. They are frozen in `strategies.yaml`. Changing a parameter creates a new strategy and increases the trial count.
2. **Sources are cited by author, year and venue.** Links and access dates are collected after a manual check (see "Status" below). The catalog contains definitions only, no performance results.
3. **Negative controls are included** (random entry, always flat, martingale, grid) to measure the verifier's own false-positive rate.
4. **A strategy being listed is not an endorsement.** Popularity is the selection rule, not performance.

## Status (phase 1, 2026-11-08)

- Definitions and parameters were written from the literature. In the 2026-11-08 check, 3 definitions were confirmed against secondary sources, 6 partially, and the other 91 are marked `unverified` (see the `verification` field). No primary full text was read. Each card must be verified before the strategy is run (phase 2, first task).
- Reference links and access dates are **not yet verified**; the type references are citations (author, year, title, venue) only.
- `build_catalog.py` validates the YAML (ids, types, trap codes, 100-entry cap, 30-entry cap of the extension) and regenerates `cards/`, `INDEX.md` and `TYPES.md`. Edit the YAML, never the generated files. Requires PyYAML.
