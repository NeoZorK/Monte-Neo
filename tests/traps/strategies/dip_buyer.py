"""HONEST code on unadjusted data: buys after a drop of more than 20% over three bars and holds for five bars."""



def signal(df):
    drop = (df["close"] / df["close"].shift(3) - 1.0).fillna(0.0)
    signal_on = (drop < -0.2).astype(float).rolling(5, min_periods=1).max()
    return signal_on.to_numpy()
