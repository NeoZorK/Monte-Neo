# Strategy and benchmark types

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

Generated from `types.yaml`. Check names marked PLAN are proposed in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

<a id="passive_index"></a>
## Buy-and-hold / passive cap-weighted index

*Family: benchmark. Catalog entries: 3.*

Hold a broad market-cap-weighted index (or one asset) with dividends reinvested. It is the null hypothesis every active strategy must beat after costs and risk.

**How it is measured**

- Metrics: CAGR, volatility, Sharpe, max drawdown, time under water, total-return series incl. dividends
- Benchmark: Itself; for others, the matching total-return index (equities) or spot asset (crypto)
- Horizon: At least one full market cycle (10+ years for equities; crypto has under 2 full cycles)

**Typical traps**

- Survivorship bias: Universe contains only assets that survived to today; delisted losers are missing.
- Corporate actions: Splits, dividends and spin-offs not handled; adjusted vs unadjusted prices mixed.
- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.

**Monte-Neo checks to apply:** data_integrity, benchmark, regime_split

**Data needed:** Total-return daily prices, dividends or adjusted close

**Monte-Neo cannot verify:**

- Whether the sample period is representative; future returns

**Key references:** Sharpe 1991 "The Arithmetic of Active Management" FAJ, Bogle 2005 "The Mutual Fund Industry 60 Years Later" FAJ

<a id="balanced_60_40"></a>
## 60/40 and static multi-asset allocation

*Family: allocation. Catalog entries: 3.*

Fixed weights across equities and bonds (and sometimes gold, commodities, REITs), rebalanced on a schedule.

**How it is measured**

- Metrics: CAGR, Sharpe, max drawdown, stock-bond correlation, rebalancing bonus, risk contribution by asset
- Benchmark: The same weights without rebalancing; 100% equity; cash
- Horizon: 20+ years; stock-bond correlation changes sign across eras

**Typical traps**

- Rebalancing convention: Result depends on rebalance frequency, thresholds and whether drift or costs are modelled.
- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Vendor / index construction effects: Result depends on a proprietary index methodology or vendor-specific adjustment.
- Taxes: After-tax return differs materially (turnover, short-term gains, withholding).

**Monte-Neo checks to apply:** data_integrity, benchmark, rebalance_sensitivity, regime_split

**Data needed:** Total-return series of each sleeve, rebalance dates

**Monte-Neo cannot verify:**

- Correlation regime in the future; tax drag; bond index substitution (ETF vs index)

**Key references:** Perold and Sharpe 1988 "Dynamic Strategies for Asset Allocation" FAJ, Asness Frazzini Pedersen 2012 "Leverage Aversion and Risk Parity" FAJ

<a id="risk_parity"></a>
## Risk parity / inverse-volatility / equal risk contribution

*Family: allocation. Catalog entries: 3.*

Weights set so each asset contributes equal risk (inverse volatility or full covariance ERC), usually levered to a target volatility.

**How it is measured**

- Metrics: Sharpe, vol-targeting realized vs target, max drawdown, leverage used, financing cost
- Benchmark: 60/40 and equal weight at matched volatility
- Horizon: Includes a rising-rate era and a stock-bond correlation flip

**Typical traps**

- Leverage and margin: Reported return relies on leverage that is unavailable or can trigger liquidation.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Rebalancing convention: Result depends on rebalance frequency, thresholds and whether drift or costs are modelled.

**Monte-Neo checks to apply:** benchmark, leverage_audit, rebalance_sensitivity, regime_split

**Data needed:** Daily total returns of sleeves, financing rate

**Monte-Neo cannot verify:**

- Cost of leverage obtainable by the user; futures vs ETF implementation differences

**Key references:** Qian 2005 "Risk Parity Portfolios" PanAgora, Maillard Roncalli Teiletche 2010 "The Properties of Equally Weighted Risk Contribution Portfolios" JPM, Asness Frazzini Pedersen 2012 FAJ

<a id="equal_weight"></a>
## Equal weight (1/N) and naive diversification

*Family: allocation. Catalog entries: 1.*

Hold N assets with weight 1/N, periodically rebalanced.

**How it is measured**

- Metrics: Sharpe, turnover, concentration vs cap-weight, small-cap tilt
- Benchmark: Cap-weighted index of the same universe
- Horizon: 10+ years

**Typical traps**

- Survivorship bias: Universe contains only assets that survived to today; delisted losers are missing.
- Rebalancing convention: Result depends on rebalance frequency, thresholds and whether drift or costs are modelled.
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.
- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.

**Monte-Neo checks to apply:** data_integrity, benchmark, universe_pit, capacity_estimate

**Data needed:** Constituent history with point-in-time membership

**Monte-Neo cannot verify:**

- Illiquidity of small constituents at scale

**Key references:** DeMiguel Garlappi Uppal 2009 "Optimal Versus Naive Diversification" RFS

<a id="minimum_variance"></a>
## Minimum variance / max diversification / HRP

*Family: allocation. Catalog entries: 4.*

Optimizer-based weights from a covariance estimate (minimum variance, most-diversified, hierarchical risk parity).

**How it is measured**

- Metrics: Realized volatility vs equal weight, Sharpe, turnover, estimation window sensitivity
- Benchmark: Equal weight and cap-weight of the same universe
- Horizon: 10+ years, out of sample with expanding covariance window

**Typical traps**

- Parameter overfitting: Parameters tuned on the same sample used to report performance.
- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Rebalancing convention: Result depends on rebalance frequency, thresholds and whether drift or costs are modelled.
- Data snooping / multiple testing: Many variants tried; the best one looks significant by chance.

**Monte-Neo checks to apply:** pbo, benchmark, rebalance_sensitivity

**Data needed:** Return panel of 20+ assets

**Monte-Neo cannot verify:**

- Covariance stability in the future

**Key references:** Clarke de Silva Thorley 2006 "Minimum-Variance Portfolios in the U.S. Equity Market" JPM, Choueifaty Coignard 2008 "Toward Maximum Diversification" JPM, Lopez de Prado 2016 "Building Diversified Portfolios that Outperform Out of Sample" JPM

<a id="factor_premia"></a>
## Factor / smart-beta (value, momentum, quality, low-vol, size)

*Family: factor. Catalog entries: 10.*

Long-only or long-short portfolios sorted on a characteristic (book-to-market, past return, profitability, beta, market cap).

**How it is measured**

- Metrics: Factor alpha vs market and other factors, t-stat with multiple-testing haircut, turnover, capacity, drawdowns
- Benchmark: Cap-weighted market; Fama-French / AQR factor regressions
- Horizon: Decades; factor premia are multi-year bets

**Typical traps**

- Point-in-time fundamentals: Fundamentals used with their period-end date instead of their publication date, or restated.
- Survivorship bias: Universe contains only assets that survived to today; delisted losers are missing.
- Post-publication decay: Anomaly weakened after academic publication or crowding.
- Data snooping / multiple testing: Many variants tried; the best one looks significant by chance.
- Short-sale cost and availability: Borrow fees, locates and recalls are ignored for the short leg.
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.
- Crash / momentum-crash risk: Large drawdown clustered in market rebounds or crises.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.

**Monte-Neo checks to apply:** dsr, pbo, alpha_after_beta, pre_post_publication_split, pit_contract

**Data needed:** Point-in-time fundamentals, delisting-adjusted returns, borrow costs

**Monte-Neo cannot verify:**

- Whether the premium persists; proprietary factor definitions

**Key references:** Fama French 1993 "Common risk factors in the returns on stocks and bonds" JFE, Carhart 1997 JF, Novy-Marx 2013 JFE, Asness Frazzini Pedersen 2019 "Quality minus junk" RAST, Harvey Liu Zhu 2016 "...and the cross-section of expected returns" RFS, McLean Pontiff 2016 JF, Hou Xue Zhang 2020 RFS

<a id="trend_following"></a>
## Trend following / time-series momentum / CTA

*Family: trend. Catalog entries: 18.*

Go long assets with positive past return (or price above a moving average / breakout), short or flat otherwise, often volatility-scaled and diversified across many markets.

**How it is measured**

- Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown
- Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index
- Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets

**Typical traps**

- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Parameter overfitting: Parameters tuned on the same sample used to report performance.
- Small sample / few independent bets: Too few trades or independent observations for a significance claim.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Futures roll yield: Continuous contract built by naive stitching hides roll cost or gain.
- Execution timing: Trade assumed at the close/open that generated the signal.

**Monte-Neo checks to apply:** benchmark, alpha_after_beta, dsr, timing, regime_split, roll_audit

**Data needed:** Daily OHLCV; continuous futures with roll rules for non-crypto

**Monte-Neo cannot verify:**

- Diversification across markets when only one asset is supplied; futures margin details

**Key references:** Moskowitz Ooi Pedersen 2012 "Time series momentum" JFE, Hurst Ooi Pedersen 2017 "A Century of Evidence on Trend-Following Investing" JPM, Brock Lakonishok LeBaron 1992 JF, Kim Tse Wald 2016 "Time series momentum and volatility scaling" JFM

<a id="xs_momentum"></a>
## Cross-sectional momentum and reversal

*Family: factor. Catalog entries: 6.*

Rank assets by past return; long winners and short losers (momentum, 12-1 months) or the opposite at 1-week/1-month horizons (reversal).

**How it is measured**

- Metrics: Long-short Sharpe, alpha vs factors, momentum-crash drawdowns, turnover, net-of-cost return
- Benchmark: Market and Fama-French plus UMD
- Horizon: Decades; reversal is a short-horizon, high-turnover effect

**Typical traps**

- Survivorship bias: Universe contains only assets that survived to today; delisted losers are missing.
- Crash / momentum-crash risk: Large drawdown clustered in market rebounds or crises.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Short-sale cost and availability: Borrow fees, locates and recalls are ignored for the short leg.
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.
- Stale prices / illiquid quotes: Last trade used as executable price in thin markets.
- Look-ahead bias: Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals).

**Monte-Neo checks to apply:** dsr, tail_skew_profile, borrow_model, universe_pit, alpha_after_beta

**Data needed:** Daily returns of a point-in-time universe, borrow cost

**Monte-Neo cannot verify:**

- Crash timing; short availability

**Key references:** Jegadeesh Titman 1993 JF, Jegadeesh 1990 JF, Lehmann 1990 QJE, Daniel Moskowitz 2016 "Momentum crashes" JFE, Barroso Santa-Clara 2015 "Momentum has its moments" JFE

<a id="mean_reversion"></a>
## Short-term mean reversion (single instrument)

*Family: mean_reversion. Catalog entries: 6.*

Buy oversold / sell overbought using oscillators, z-scores or bands, with a quick exit.

**How it is measured**

- Metrics: Win rate, payoff ratio, expectancy per trade, max adverse excursion, tail loss, time in market
- Benchmark: Buy-and-hold and a random-entry null with the same holding time
- Horizon: Many independent trades; drawdown clustered in trends

**Typical traps**

- Risk of ruin: Position sizing can lose the whole account (martingale, averaging down).
- Short-volatility tail / negative skew: Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Parameter overfitting: Parameters tuned on the same sample used to report performance.
- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Stale prices / illiquid quotes: Last trade used as executable price in thin markets.

**Monte-Neo checks to apply:** timing, dsr, costs, tail_skew_profile, ruin_probability

**Data needed:** Daily OHLCV

**Monte-Neo cannot verify:**

- Intraday excursion beyond daily bars

**Key references:** Connors Alvarez 2008 "Short Term Trading Strategies That Work", Lo MacKinlay 1990 RFS, Bollinger 2001 "Bollinger on Bollinger Bands"

<a id="stat_arb_pairs"></a>
## Statistical arbitrage and pairs trading

*Family: relative_value. Catalog entries: 7.*

Trade the spread between related assets that is assumed stationary (distance, cointegration, Ornstein-Uhlenbeck, PCA residuals).

**How it is measured**

- Metrics: Net Sharpe, spread half-life, stationarity tests out of sample, leg-level P&L, borrow cost, turnover
- Benchmark: Market-neutral zero; randomly paired null; per-leg buy-and-hold
- Horizon: Includes regime breaks; formation and trading windows separated

**Typical traps**

- Pair / universe selection bias: Pairs chosen by looking at the full sample are guaranteed to look cointegrated.
- Cointegration breakdown: Spread stops mean-reverting; the relation was selected in-sample.
- Short-sale cost and availability: Borrow fees, locates and recalls are ignored for the short leg.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Execution timing: Trade assumed at the close/open that generated the signal.
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.
- Survivorship bias: Universe contains only assets that survived to today; delisted losers are missing.

**Monte-Neo checks to apply:** cointegration_suite, pair_selection_bias, legging_audit, dsr, borrow_model

**Data needed:** Aligned adjusted prices of both legs, borrow rates, liquidity

**Monte-Neo cannot verify:**

- Fundamental reason a spread should hold; legging risk without intraday data

**Key references:** Gatev Goetzmann Rouwenhorst 2006 RFS, Engle Granger 1987 Econometrica, Elliott van der Hoek Malcolm 2005 Quant. Finance, Avellaneda Lee 2010 Quant. Finance, Do Faff 2010 "Does simple pairs trading still work?" FAJ

<a id="market_making"></a>
## Market making / liquidity provision

*Family: microstructure. Catalog entries: 1.*

Quote both sides, earn the spread, manage inventory and adverse selection.

**How it is measured**

- Metrics: Spread capture, adverse selection (markout), inventory risk, fill ratio, fees and rebates, latency sensitivity
- Benchmark: Zero; quoting at the touch with no skew
- Horizon: Intraday to weeks; many fills

**Typical traps**

- Unrealistic execution model: Fills at mid, no queue position, no partial fills, no latency.
- Look-ahead bias: Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals).
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.
- Short-volatility tail / negative skew: Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.

**Monte-Neo checks to apply:** verify_quotes (existing), execution_model_audit

**Data needed:** Level-2 or quote/trade tape with timestamps

**Monte-Neo cannot verify:**

- Queue position without full order-book data; daily bars are not enough

**Key references:** Avellaneda Stoikov 2008 "High-frequency trading in a limit order book" Quant. Finance, Glosten Milgrom 1985 JFE

<a id="carry"></a>
## Carry (FX, commodity roll, bond roll-down, crypto funding/basis)

*Family: carry. Catalog entries: 4.*

Earn the yield differential or roll return from holding higher-yielding exposure funded by lower-yielding exposure.

**How it is measured**

- Metrics: Carry return vs spot return decomposition, Sharpe, skew, crash drawdowns, funding sign flips, margin usage
- Benchmark: Spot/buy-and-hold; cash
- Horizon: Includes a crisis (2008 FX, 2020 and 2022 crypto)

**Typical traps**

- Short-volatility tail / negative skew: Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail.
- Funding rate and basis risk: Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series.
- Futures roll yield: Continuous contract built by naive stitching hides roll cost or gain.
- Leverage and margin: Reported return relies on leverage that is unavailable or can trigger liquidation.
- Crash / momentum-crash risk: Large drawdown clustered in market rebounds or crises.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.

**Monte-Neo checks to apply:** carry_decomposition, tail_skew_profile, roll_audit, leverage_audit, smoothing

**Data needed:** Spot and forward/futures or perpetual prices, funding history, interest rates

**Monte-Neo cannot verify:**

- Counterparty/exchange default; margin calls from intraday spikes

**Key references:** Koijen Moskowitz Pedersen Vrugt 2018 "Carry" JFE, Lustig Roussanov Verdelhan 2011 RFS, Gorton Rouwenhorst 2006 FAJ, Schmeling Schrimpf Todorov 2023 "Crypto Carry" BIS WP 1087

<a id="short_volatility"></a>
## Volatility selling / short vol

*Family: volatility. Catalog entries: 4.*

Collect the variance risk premium by selling options or shorting volatility products; payoff is concave with a severe left tail.

**How it is measured**

- Metrics: Skew, kurtosis, CVaR 1%/5%, worst day/month, Sharpe adjusted for skew (e.g. Sortino, Omega), time to recover, stress replays (Feb 2018 XIV, Mar 2020)
- Benchmark: Equity index; put-write index; cash
- Horizon: Must include a vol-spike event; otherwise the sample is uninformative

**Typical traps**

- Short-volatility tail / negative skew: Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail.
- Return smoothing / stale marks: Serial correlation or stale prices understate volatility and inflate Sharpe.
- Leverage and margin: Reported return relies on leverage that is unavailable or can trigger liquidation.
- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Risk of ruin: Position sizing can lose the whole account (martingale, averaging down).
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Unrealistic execution model: Fills at mid, no queue position, no partial fills, no latency.

**Monte-Neo checks to apply:** tail_skew_profile, stress_replay, smoothing, alpha_after_beta, ruin_probability

**Data needed:** Option chains or VIX futures history, underlying prices

**Monte-Neo cannot verify:**

- Gap and liquidity events not in the sample; early assignment details with daily data

**Key references:** Carr Wu 2009 "Variance Risk Premiums" RFS, Bondarenko 2014 "Why are put options so expensive?" QJFin, Coval Shumway 2001 JF, Whaley 2002 "Return and risk of CBOE Buy Write Monthly Index" JD

<a id="options_overlay"></a>
## Options overlays (covered call, put-write, collar, protective put)

*Family: volatility. Catalog entries: 3.*

Hold the underlying and add short calls/puts or protective puts on a fixed rule.

**How it is measured**

- Metrics: Return vs underlying at matched beta, upside capture, downside capture, Sharpe, drawdown
- Benchmark: Underlying total-return index; beta-matched equity plus cash
- Horizon: Full cycle including a strong rally and a crash

**Typical traps**

- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Short-volatility tail / negative skew: Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail.
- Unrealistic execution model: Fills at mid, no queue position, no partial fills, no latency.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Taxes: After-tax return differs materially (turnover, short-term gains, withholding).

**Monte-Neo checks to apply:** benchmark, alpha_after_beta, tail_skew_profile

**Data needed:** Option chains (bid/ask) or published overlay-index series

**Monte-Neo cannot verify:**

- Fills at mid; early exercise; the tax treatment

**Key references:** Whaley 2002 JD, Israelov Nielsen 2014 "Covered Call Strategies: One Fact and Eight Myths" FAJ

<a id="event_merger_arb"></a>
## Merger arbitrage and event-driven

*Family: event. Catalog entries: 3.*

Buy the target of an announced deal at a discount to the offer; collect the spread when the deal closes. Related: PEAD, index inclusion.

**How it is measured**

- Metrics: Annualized spread return, deal-break loss, hit rate, correlation to market in down-markets, event study CARs
- Benchmark: Market and risk-free rate; hedge-fund merger arb index
- Horizon: Includes a merger-boom and a bust; deal-level sample size

**Typical traps**

- Short-volatility tail / negative skew: Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail.
- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Survivorship bias: Universe contains only assets that survived to today; delisted losers are missing.
- Look-ahead bias: Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals).
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Point-in-time fundamentals: Fundamentals used with their period-end date instead of their publication date, or restated.

**Monte-Neo checks to apply:** tail_skew_profile, alpha_after_beta, event_study_audit

**Data needed:** Deal database with announcement timestamps, prices around events

**Monte-Neo cannot verify:**

- Legal and regulatory risk; deal-specific information

**Key references:** Mitchell Pulvino 2001 "Characteristics of Risk and Return in Risk Arbitrage" JF, Bernard Thomas 1989 JAR

<a id="convertible_arb"></a>
## Convertible arbitrage

*Family: relative_value. Catalog entries: 1.*

Long convertible bond, short the underlying stock (delta hedge), harvest cheap implied volatility and carry.

**How it is measured**

- Metrics: Net return, credit spread beta, liquidity-crisis drawdown, gamma P&L, smoothing of reported returns
- Benchmark: Credit and equity indices; hedge-fund index
- Horizon: Includes 2008 and 2020

**Typical traps**

- Return smoothing / stale marks: Serial correlation or stale prices understate volatility and inflate Sharpe.
- Stale prices / illiquid quotes: Last trade used as executable price in thin markets.
- Leverage and margin: Reported return relies on leverage that is unavailable or can trigger liquidation.
- Short-volatility tail / negative skew: Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail.
- Short-sale cost and availability: Borrow fees, locates and recalls are ignored for the short leg.
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.

**Monte-Neo checks to apply:** smoothing, tail_skew_profile, leverage_audit

**Data needed:** Convertible prices (often indicative), stock borrow, credit spreads

**Monte-Neo cannot verify:**

- Reproducing a convertible book from public OHLCV; model-dependent marks

**Key references:** Agarwal Fung Loon Naik 2011 "Risk and return in convertible arbitrage" J. Empirical Finance

<a id="global_macro"></a>
## Global macro (discretionary and systematic)

*Family: macro. Catalog entries: 2.*

Directional positions across rates, FX, commodities and equities driven by macro views. Systematic variants use rule-based growth/inflation regimes.

**How it is measured**

- Metrics: Sharpe, regime-conditional return, beta to risk assets, hit rate, decision log
- Benchmark: Diversified risk-parity and trend indices
- Horizon: Full cycles; sparse independent macro events

**Typical traps**

- Discretionary / non-rule-based: No reproducible rule; cannot be backtested honestly.
- Small sample / few independent bets: Too few trades or independent observations for a significance claim.
- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Look-ahead bias: Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals).
- Data snooping / multiple testing: Many variants tried; the best one looks significant by chance.

**Monte-Neo checks to apply:** dsr, alpha_after_beta, regime_split, holdout

**Data needed:** Point-in-time macro releases (with release dates), market prices

**Monte-Neo cannot verify:**

- Discretionary judgement; revised macro data used as if known at the time

**Key references:** Fung Hsieh 2001 "The Risk in Hedge Fund Strategies" RFS, Bridgewater All Weather public description

<a id="long_short_equity"></a>
## Long/short equity

*Family: factor. Catalog entries: 1.*

Long selected stocks, short others; net exposure varies.

**How it is measured**

- Metrics: Net and gross exposure, beta, alpha, short-leg contribution, borrow cost, turnover
- Benchmark: Market, sector, and factor returns
- Horizon: Multi-year, includes crashes

**Typical traps**

- Short-sale cost and availability: Borrow fees, locates and recalls are ignored for the short leg.
- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Survivorship bias: Universe contains only assets that survived to today; delisted losers are missing.
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.
- Point-in-time fundamentals: Fundamentals used with their period-end date instead of their publication date, or restated.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.

**Monte-Neo checks to apply:** alpha_after_beta, borrow_model, universe_pit, dsr

**Data needed:** Equity panel with delistings, borrow rates, sector map

**Monte-Neo cannot verify:**

- Stock-picking skill from narrative; locates and recalls

**Key references:** Ackermann McEnally Ravenscraft 1999 "The Performance of Hedge Funds" JF, Fama French 2015 RFS

<a id="calendar_anomaly"></a>
## Calendar and seasonal effects

*Family: calendar. Catalog entries: 4.*

Systematic return patterns by day of week, month, holiday, or overnight vs intraday.

**How it is measured**

- Metrics: Mean excess return in window, t-stat with multiple-testing correction, out-of-sample persistence, net of costs
- Benchmark: Unconditional average return of the same asset
- Horizon: Decades; effects are small and fragile

**Typical traps**

- Data snooping / multiple testing: Many variants tried; the best one looks significant by chance.
- Post-publication decay: Anomaly weakened after academic publication or crowding.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Small sample / few independent bets: Too few trades or independent observations for a significance claim.

**Monte-Neo checks to apply:** dsr, pre_post_publication_split, costs, holdout

**Data needed:** Daily OHLC (open and close needed for overnight/intraday split)

**Monte-Neo cannot verify:**

- Causal reasons; stability in the future

**Key references:** French 1980 JFE, Ariel 1987 JF, Lakonishok Smidt 1988 RFS, Bouman Jacobsen 2002 AER, Cooper Cliff Gulen 2008 "Return Differences between Trading and Non-Trading Hours" SSRN, Sullivan Timmermann White 2001 JF

<a id="vol_managed"></a>
## Volatility targeting / managed portfolios

*Family: overlay. Catalog entries: 2.*

Scale exposure inversely to recent realized volatility to hold risk constant.

**How it is measured**

- Metrics: Sharpe vs unmanaged, realized vol vs target, turnover, drawdown, leverage
- Benchmark: Same asset unmanaged and at matched average leverage
- Horizon: Includes vol-clustering episodes

**Typical traps**

- Look-ahead bias: Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals).
- Leverage and margin: Reported return relies on leverage that is unavailable or can trigger liquidation.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Parameter overfitting: Parameters tuned on the same sample used to report performance.
- Execution timing: Trade assumed at the close/open that generated the signal.

**Monte-Neo checks to apply:** lookahead, timing, benchmark, costs

**Data needed:** Daily returns

**Monte-Neo cannot verify:**

- Gap risk between rebalances

**Key references:** Moreira Muir 2017 "Volatility-Managed Portfolios" JF, Harvey et al. 2018 "The Impact of Volatility Targeting" JPM

<a id="rebalancing_policy"></a>
## Rebalancing and glide-path policies (constant-mix, CPPI, target-date)

*Family: allocation. Catalog entries: 3.*

Rule-based change of weights over time or with wealth/risk (constant-mix, portfolio insurance, glide path to retirement date).

**How it is measured**

- Metrics: Terminal wealth distribution, shortfall probability, path dependence, turnover, cost drag
- Benchmark: Buy-and-hold with the same initial weights
- Horizon: Investor lifetime; needs simulated and historical paths

**Typical traps**

- Rebalancing convention: Result depends on rebalance frequency, thresholds and whether drift or costs are modelled.
- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Taxes: After-tax return differs materially (turnover, short-term gains, withholding).
- Small sample / few independent bets: Too few trades or independent observations for a significance claim.

**Monte-Neo checks to apply:** rebalance_sensitivity, monte_carlo paths (existing engine), benchmark

**Data needed:** Return series of sleeves; contribution schedule

**Monte-Neo cannot verify:**

- Investor behaviour; the tax and lifetime-income context

**Key references:** Black Jones 1987 "Simplifying Portfolio Insurance" JPM, Perold Sharpe 1988 FAJ

<a id="dca"></a>
## Dollar-cost averaging and value averaging

*Family: allocation. Catalog entries: 2.*

Invest a fixed amount per period (DCA) or follow a target-path of portfolio value (value averaging).

**How it is measured**

- Metrics: Money-weighted return (IRR), terminal wealth vs lump sum, regret, drawdown of invested capital
- Benchmark: Lump-sum investment at the first date; cash-held share
- Horizon: Multi-year contribution schedule

**Typical traps**

- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Costs: Edge disappears under realistic transaction costs, spread, borrow and funding.
- Small sample / few independent bets: Too few trades or independent observations for a significance claim.

**Monte-Neo checks to apply:** benchmark, regime_split

**Data needed:** Price series; contribution schedule

**Monte-Neo cannot verify:**

- Investor cash flows in reality; behavioural effects

**Key references:** Constantinides 1979 "A Note on the Suboptimality of Dollar-Cost Averaging" JFQA, Edleson 1991 "Value Averaging"

<a id="crypto_specific"></a>
## Crypto-specific (perpetual funding, basis, cross-sectional crypto momentum)

*Family: carry. Catalog entries: 5.*

Strategies exploiting perpetual swap funding, spot-futures basis, or cross-sectional crypto returns.

**How it is measured**

- Metrics: Net of funding and fees, exchange-risk-adjusted return, drawdown, tail skew, capacity
- Benchmark: BTC/ETH buy-and-hold; stablecoin yield
- Horizon: Short history (2017+); covers few regimes

**Typical traps**

- Funding rate and basis risk: Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series.
- Hidden market beta: Reported return is mostly exposure to the market or a known factor, not skill.
- Survivorship bias: Universe contains only assets that survived to today; delisted losers are missing.
- Short-volatility tail / negative skew: Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail.
- Capacity / liquidity: Strategy cannot be traded at size without moving the price.
- Regime dependence: Works only in one market regime (e.g. a bull market) in the sample.
- Small sample / few independent bets: Too few trades or independent observations for a significance claim.

**Monte-Neo checks to apply:** carry_decomposition, alpha_after_beta, universe_pit, regime_split, dsr

**Data needed:** Spot and perp OHLCV, funding history, delisted-coin history

**Monte-Neo cannot verify:**

- Exchange insolvency
- depeg events outside the price series

**Key references:** Liu Tsyvinski 2021 "Risks and Returns of Cryptocurrency" RFS, Liu Tsyvinski Wu 2022 "Common Risk Factors in Cryptocurrency" JF, Schmeling Schrimpf Todorov 2023 BIS WP 1087

<a id="controls"></a>
## Negative controls and null strategies

*Family: control. Catalog entries: 4.*

Random entry with matched holding time, always-flat, and ruinous retail patterns (martingale, grid) included to calibrate the verifier and show what failure looks like.

**How it is measured**

- Metrics: Verdict distribution, false-positive rate of the verifier
- Benchmark: Verifier expectation (should not PASS)
- Horizon: Same as the catalog

**Typical traps**

- Risk of ruin: Position sizing can lose the whole account (martingale, averaging down).
- Data snooping / multiple testing: Many variants tried; the best one looks significant by chance.
- Parameter overfitting: Parameters tuned on the same sample used to report performance.

**Monte-Neo checks to apply:** dsr, ruin_probability, timing

**Data needed:** Daily OHLCV

**Monte-Neo cannot verify:**

- Nothing special; they exist to measure verifier calibration

**Key references:** Bailey Lopez de Prado 2014 "The Deflated Sharpe Ratio" JPM, Bailey Borwein Lopez de Prado Zhu 2017 "The Probability of Backtest Overfitting" JCF

