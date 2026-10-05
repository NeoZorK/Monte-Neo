# Repainting: signals that change after they were shown

A signal *repaints* when what the chart shows afterwards differs from what a trader saw at the time. A backtest of
such a signal earns money nobody could have earned. Two different things can repaint, and Monte-Neo checks both.

## History: `repaint_history`

The signal of a closed bar must stay the same when more bars arrive. The check compares the signals of prefixes that
follow one another (the table as it grew), the table extended by synthetic bars, and the table with its last three bars
restated. Any difference fails the check, which rejects the strategy, and the details say how many bars were redrawn,
how far back, and where it started.

Typical sources: ZigZag and swing pivots that a later bar confirms, Williams fractals without a confirmation delay,
`rolling(center=True)`, Ichimoku's lagging span, whole-series statistics, `find_peaks` over the whole array, a
higher-timeframe bar used before it closed.

`--repaint auto` (the default) uses about a dozen prefixes plus the last bars; `strict` uses about four times as many;
`off` skips both repaint checks.

## The forming bar: `repaint_live`

The bar's high, low, close and volume are replaced by their state at 0, 25, 50 and 75 % of the bar, along a path
open -> low -> high -> close (an up bar) or open -> high -> low -> close (a down bar).

* A signal that cannot change in any of these states is **known at the bar's open** (it only reads closed bars): pass.
* A signal that changes is **decided at the close**. That is how every rule on the close works, and it is not a fault: act
  on it only after the bar closed, never on the forming bar. The check reports the flicker rate as information.
* With `--signal-timing open` you declare that the signal is known at the open. A signal that needs the bar's own
  prices then fails.

The engine always fills a signal on the next bar, so a closed-bar strategy is not credited with the bar it decided on.

## Lint rules and fixes

`repaint_zigzag`, `unconfirmed_pivot` (`find_peaks`, `argrelextrema`), `htf_without_shift` (a `resample(...)`
aggregate not shifted before it is used on lower-timeframe bars) and `lookahead_on` are warnings. `monte-neo verify
--suggest-fix` shifts a higher-timeframe aggregate by one bar and switches `lookahead` off.

## In `discover`

Every candidate and every canary passes the same gate; the gate also appends bars and restates the last ones. The
winner's certificate carries both repaint rows, and the result reports `confirmation: close`.
