"""A14: signals that repaint (history) or depend on the forming bar, and honest twins.

Each row: (id, source of signal(df), repaints history, known at the bar's open).
"""

from __future__ import annotations

HEAD = "import numpy as np\nimport pandas as pd\nimport scipy.signal\n\n\ndef signal(df):\n    c = df['close']\n    h = df['high']\n    l = df['low']\n"
DAY = "df['timestamp'].dt.date"


def _src(body: str) -> str:
    return HEAD + "".join(f"    {line}\n" for line in body.strip().splitlines())


# --- repainters: the signal of a closed bar changes when later bars arrive ---------------------------------------------
REPAINTERS = [
    ("zigzag_pivots", """
lo = (l == l.rolling(9, center=True).min())
hi = (h == h.rolling(9, center=True).max())
pos = pd.Series(np.where(lo, 1.0, np.where(hi, -1.0, np.nan)), index=df.index).ffill().fillna(0.0)
return pos
"""),
    ("fractal_unconfirmed", """
up = (h > h.shift(-1)) & (h > h.shift(-2)) & (h > h.shift(1)) & (h > h.shift(2))
dn = (l < l.shift(-1)) & (l < l.shift(-2)) & (l < l.shift(1)) & (l < l.shift(2))
return pd.Series(np.where(dn, 1.0, np.where(up, -1.0, np.nan)), index=df.index).ffill().fillna(0.0)
"""),
    ("centered_sma", "return (c > c.rolling(11, center=True).mean()).astype(int)"),
    ("chikou_span", "return (c.shift(-8) > c).astype(int)"),
    ("find_peaks_whole", """
peaks, _ = scipy.signal.find_peaks(c.to_numpy())
troughs, _ = scipy.signal.find_peaks(-c.to_numpy())
pos = np.full(len(c), np.nan)
pos[peaks] = -1.0
pos[troughs] = 1.0
return pd.Series(pos, index=df.index).ffill().fillna(0.0)
"""),
    ("whole_sample_zscore", "return ((c - c.mean()) / c.std() > 0).astype(int)"),
    ("htf_day_last_unshifted", f"return (c.groupby({DAY}).transform('last') > c).astype(int)"),
    ("htf_day_high_unshifted", f"return (h.groupby({DAY}).transform('max') > h.rolling(24).mean()).astype(int)"),
    ("last_row_reference", "return (c > c.iloc[-1]).astype(int)"),
    ("expanding_then_global_rank", "return (c.rank(pct=True) > 0.5).astype(int)"),
    ("swing_high_future_bars", """
swing = (h.shift(-1) < h) & (h > h.shift(1))
trough = (l.shift(-1) > l) & (l < l.shift(1))
return pd.Series(np.where(swing, -1.0, np.where(trough, 1.0, np.nan)), index=df.index).ffill().fillna(0.0)
"""),
    ("bfill_gap_signal", "return (c.where(c.rolling(5).mean() > c).bfill() > c).astype(int)"),
]

# --- honest twins: closed bars never move -----------------------------------------------------------------------------
# The third column says whether the signal is known at the bar's open (does not read the bar's own prices).
HONEST = [
    ("sma_cross_on_close", "return (c > c.rolling(20).mean()).astype(int)", False),
    ("sma_cross_lagged", "p = c.shift(1)\nreturn (p > p.rolling(20).mean()).astype(int)", True),
    ("confirmed_fractal", """
p = h.shift(2)
up = (p > h.shift(1)) & (p > h.shift(3)) & (p > h) & (p > h.shift(4))
q = l.shift(2)
dn = (q < l.shift(1)) & (q < l.shift(3)) & (q < l) & (q < l.shift(4))
return pd.Series(np.where(dn, 1.0, np.where(up, -1.0, np.nan)), index=df.index).ffill().fillna(0.0)
""", False),
    ("confirmed_zigzag_shifted", """
lo = (l == l.rolling(9, center=True).min())
hi = (h == h.rolling(9, center=True).max())
pos = pd.Series(np.where(lo, 1.0, np.where(hi, -1.0, np.nan)), index=df.index).ffill().fillna(0.0)
return pos.shift(5).fillna(0.0)
""", True),
    ("expanding_return_zscore", "r = c.pct_change()\nreturn ((r - r.expanding().mean()) / r.expanding().std() > 0).astype(int)", False),
    ("htf_day_last_shifted", f"return (c.groupby({DAY}).transform('last').shift(24) < c.shift(1)).astype(int)", True),
    ("rsi_like", """
d = c.diff()
up = d.clip(lower=0).rolling(14).mean()
dn = (-d.clip(upper=0)).rolling(14).mean()
return (up / dn > 1.0).astype(int)
""", False),
    ("ema_lagged", "return (c.shift(1) > c.shift(1).ewm(span=30, adjust=False).mean()).astype(int)", True),
    ("donchian_breakout_lagged", "return (c.shift(1) > h.shift(2).rolling(20).max()).astype(int)", True),
    ("volume_filter_closed_bar", "v = df['volume']\nreturn ((c > c.rolling(10).mean()) & (v > v.rolling(10).mean())).astype(int)", False),
    ("momentum_on_open", "o = df['open']\nreturn (o.shift(1) > o.shift(11)).astype(int)", True),
]

CASES = [(i, _src(b), True, False) for i, b in REPAINTERS] + [(i, _src(b), False, k) for i, b, k in HONEST]
