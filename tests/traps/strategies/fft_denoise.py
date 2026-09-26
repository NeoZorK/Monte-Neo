"""TRAP: FFT low-pass over the whole series; every bar depends on all future bars."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    spec = np.fft.rfft(close - close[0])
    spec[20:] = 0
    trend = np.fft.irfft(spec, n=len(close)) + close[0]
    return np.where(np.diff(trend, prepend=trend[0]) > 0, 1, -1)
