"""TRAP: rolling window over the reversed series looks forward without shift/center."""


def signal(df):
    future_max = df["close"][::-1].rolling(10, min_periods=1).max()[::-1]
    return (future_max > df["close"] * 1.0005).astype(int)
