"""HONEST: long after a return above the expanding 90% quantile; a real edge on momentum data."""


def signal(df):
    r = df["close"].pct_change()
    q = r.expanding(100).quantile(0.9).shift(1)
    return (r > q).astype(int)
