"""TRAP: centered rolling mean includes future bars."""


def signal(df):
    mid = df["close"].rolling(21, center=True).mean()
    return (df["close"] < mid).astype(int)
