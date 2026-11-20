# What the verifier covers, and what it does not

New in this release (library functions; pass their rows to `verify_strategy(extra_checks=...)` or call them directly):

| Area | Module | Check row |
|------|--------|-----------|
| Data contract | `verify.data_contract` | `publication_dates`, `universe_membership` |
| Volume-capped execution, partial fills, square-root impact | `verify.execution` | `execution_capacity` |
| Funding and borrow as rate series | `verify.funding` | `funding_borrow_stress` |
| Portfolio CVaR, risk concentration, mean and tail correlation | `verify.portfolio_risk` | `risk` block of `verify_portfolio` |

## Not covered (needs data this package does not have)

* **No point-in-time database.** `published_at` and membership intervals are taken as given; the validator proves
  consistency (nothing used before it was published, nothing traded outside membership), not that a vendor's timestamps
  or index histories are honest or complete. Restated and revised values are invisible.
* **No order book.** Execution uses bar volume and a square-root impact law with a coefficient you supply (default 1.0);
  queue position, hidden liquidity, spread dynamics inside a bar and latency are not modeled. Real quotes enter only as
  a median half-spread (`quotes_half_spread_bps`).
* **Funding and borrow** are applied to the weight held; liquidations, margin calls and borrow availability are not modeled.
* **Regimes** are labeled from trailing return and volatility of the data given, not from macro states.
* **Fee tiers** are orientation values; check the exchange's current schedule.

## Not covered in v0.55: limitations in one place

* **No point-in-time database** and **no historical order book** (see above): timestamps, membership and spreads are taken as given.
* **Options:** without a historical option chain the volatility surface as of each date, tradable strikes and open interest are not assessed.
  The stress is a European Black-Scholes reprice with the volatility you supply; margin is a simplified Reg-T style estimate; assignment and pin
  risk are warnings. A table with missing columns gets *not assessed* rows, never a pass.
* **Profiles** describe verification coverage. A profile never raises a verdict, and what it lists as not assessed stays unassessed.
* **Automatic repair** only tries a small declared set of fixes. Each one counts as a trial, is re-verified in full and cannot raise a verdict by itself.
  Bad data, survivorship and phantom profit need you.
* **Dossier evidence map** (SR 11-7, SS1/23) shows which clause has which evidence. It is not a compliance statement, a model approval or legal advice.
* **ARL and depth** rules are provisional (`arl-rules/2`); the numbers are proposals until calibrated.
* **Catalog results** are validation only with the holdout sealed; a verified row is one instance of a rule on one instrument and sample.
* **Platforms:** macOS and Linux, Python 3.11 to 3.15 (3.15 beta-supported). **Windows is prepared but unverified**: see [Platforms](../setup/platforms.md).
* Nothing here is investment advice, and no result predicts future returns.

## High-frequency strategies (holding under one minute)

Partly covered. `monte-neo verify --quotes` checks whether a profit survives the time each bid/ask quote really
arrived (stamp plus latency). Queue position, partial fills and the order book are not modelled, on purpose: a rough
formula would give false precision. A high-frequency strategy can therefore be rejected by the latency check, but it
cannot be passed on the evidence Monte-Neo has. Catalog entries of this kind carry the tag "verifiable: partly".
