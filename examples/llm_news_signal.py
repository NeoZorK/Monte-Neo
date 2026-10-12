"""A news-sentiment strategy: events are joined to bars by publication time, and the model cutoff is checked.

``ev_sentiment`` is the sentiment score of the latest news item that was already public at each bar. Synthetic events
carry ``event_time`` (when it happened) and ``published_at`` (when it appeared, a few bars later), so the verifier can
show what a join by event time would have earned (``pit_events``). ``model_cutoff`` is the training-data cutoff of the
language model that scored the news (``model_cutoff`` row).

Run: uv run python examples/llm_news_signal.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.disclaimer import SHORT
from monte_neo.verify import verify_strategy


def signal(df: pd.DataFrame) -> np.ndarray:
    """Trade the sentiment of the latest public news, only in the direction the 50-bar price trend confirms."""
    trend = np.sign(df["close"] - df["close"].rolling(50).mean()).fillna(0.0).to_numpy()
    news = np.sign(df["ev_sentiment"].fillna(0.0).to_numpy())
    return np.where(trend == news, news, 0.0)


def make_events(bars: pd.DataFrame, delay_bars: int = 3, seed: int = 0) -> pd.DataFrame:
    """Synthetic events every 40 bars; published_at = event_time + delay. Sentiment is pure noise (no edge)."""
    rng = np.random.default_rng(seed)
    stamps = pd.to_datetime(bars["timestamp"], utc=True).reset_index(drop=True)
    step = stamps.diff().median()
    idx = np.arange(20, len(bars) - delay_bars - 1, 40)
    event_time = stamps.iloc[idx].reset_index(drop=True)
    return pd.DataFrame(
        {"event_time": event_time, "published_at": event_time + delay_bars * step, "sentiment": rng.normal(0.0, 1.0, len(idx))}
    )


def bars_with_news_drift(events: pd.DataFrame, n: int = 3000, delay_bars: int = 3, seed: int = 11) -> pd.DataFrame:
    """Hourly bars where each item's sentiment moves the price over the 30 bars after it was published."""
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0, 0.004, n)
    for k, sentiment in enumerate(events["sentiment"]):
        start = 20 + 40 * k + delay_bars + 1
        ret[start : start + 30] += 0.00015 * np.sign(sentiment)
    close = 100.0 * np.exp(np.cumsum(ret))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {"timestamp": pd.date_range("2022-01-03", periods=n, freq="h"), "open": open_, "high": np.maximum(open_, close) * 1.001,
         "low": np.minimum(open_, close) * 0.999, "close": close, "volume": 1000.0}
    )


if __name__ == "__main__":
    events = make_events(pd.DataFrame({"timestamp": pd.date_range("2022-01-03", periods=3000, freq="h")}))
    bars = bars_with_news_drift(events)
    cutoff = str(pd.to_datetime(bars["timestamp"], utc=True).iloc[len(bars) // 2].date())
    report = verify_strategy(bars, strategy=__file__, events=events, model_cutoff=cutoff, n_trials=3)
    print(f"verdict: {report['verdict']}  certificate {report['certificate_id']}  (model cutoff {cutoff})")
    for row in report["checks"]:
        if row["id"] in ("pit_events", "model_cutoff"):
            print(f"  {row['id']:12s} {row['status']:5s} {row['summary']}")
    print(SHORT)
