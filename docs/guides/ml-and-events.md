# Machine-learning strategies and event data

Two leaks that no line of code shows: a model fitted on the whole file, and events joined by the time they happened
instead of the time they became public. Monte-Neo takes both decisions away from the strategy.

## The `fit` / `predict` protocol

A model fitted inside `signal(df)` on every row still reacts to its input row by row, so the look-ahead probes cannot
see that it learned from the future. Define two functions instead of `signal`:

```python
import numpy as np

REFIT_EVERY = 63     # bars between refits
MIN_TRAIN = 252      # bars before the first prediction
LABEL_HORIZON = 1    # bars a training label looks ahead
EMBARGO = 5          # extra bars between the training rows and the first predicted row


def fit(train):
    """Return any object: a fitted estimator, coefficients, a dict."""
    ...


def predict(model, df):
    """One position per row of df (+1 / 0 / -1 or weights)."""
    ...
```

```bash
monte-neo verify --ohlcv data.csv --strategy model.py
```

The verifier runs the walk-forward itself. Each block of `REFIT_EVERY` bars is predicted by a model fitted on rows
`[0, start − LABEL_HORIZON − EMBARGO)`, so no prediction comes from a model that saw its own future. The look-ahead
probes then test `predict`. Fitted models are cached by their exact training rows, so the probes do not refit for nothing.

| Check | What it says |
|-------|--------------|
| `ml_refit_gap` | The Sharpe with honest refitting against the Sharpe of `predict(fit(df), df)`, the usual whole-file backtest. `fail` (look-ahead) when the in-sample edge is real and the walk-forward loses money: the profit lived in the fit. `warn` when less than half the edge survives. |
| `ml_cv_overlap` | If the file defines `cv_splits(df)` (a list of `(train_rows, test_rows)`): training rows whose labels reach into a test fold, or that sit inside the embargo after it. Purge them. |

The constants are part of the strategy source, so they are hashed into the certificate. Setting `LABEL_HORIZON` or
`EMBARGO` lower than the truth weakens the test, and anyone who reads the source can see it.

## Events joined by publication time

Earnings surprises, news sentiment, alternative data and LLM outputs reach a strategy as events. The common leak is a join
on the event's own time (the quarter end, the moment the fact happened) instead of the time it was published.

```bash
monte-neo verify --ohlcv data.csv --strategy s.py --events events.csv [--events-delay 3600]
```

`events.csv` has `published_at` (required), `event_time` (optional), `symbol` (for universes) and numeric value columns.
The verifier joins them to the bars as `ev_<column>` columns, and the strategy reads those.

- An event is visible from the first bar that **opens after** `published_at + delay`. A bar that was already open when the
  news came out could not have used it.
- Nothing is filled before the first event.

| Check | What it says |
|-------|--------------|
| `events_quality` | Events published before they happened, a zero publication delay (is `published_at` really the publication time?), events outside the price range |
| `pit_events` | The same strategy run once more on a join by `event_time`. A warning when that join earns more than twice as much and 5 points more: most of the edge would need knowing events before they were public. |

The events go into the certificate as a hash and a delay. Recheck with the same file:
`monte-neo verify --recheck cert.json --ohlcv data.csv --strategy s.py --events events.csv`.

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not
predict future returns.
