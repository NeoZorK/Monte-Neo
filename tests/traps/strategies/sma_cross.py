"""HONEST: causal SMA crossover (no look-ahead)."""


def signal(df):
    fast = df["close"].rolling(20).mean()
    slow = df["close"].rolling(80).mean()
    return (fast > slow).astype(int)
