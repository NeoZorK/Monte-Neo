"""HONEST (grid): SMA crossover with tunable windows for verify_grid."""


def signal(df, fast=20, slow=80):
    f = df["close"].rolling(fast).mean()
    s = df["close"].rolling(slow).mean()
    return (f > s).astype(int)
