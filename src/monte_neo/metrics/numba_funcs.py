from __future__ import annotations

import numpy as np
from numba import njit, prange


@njit
def extract_trades_fast(
    prices: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    signals: np.ndarray,
    use_sl_tp: bool = False,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
    commission_pct: float = 0.0,
    slippage_pct: float = 0.0,
) -> list[tuple[int, int, float, float, int, float, float]]:
    """Fast trade extraction using Numba JIT."""
    results = []

    position = 0
    entry_idx = 0
    entry_price = 0.0

    sl_price = 0.0
    tp_price = 0.0
    
    blocked_signal = 0

    for i in range(len(signals)):
        signal = int(signals[i])
        price = prices[i]
        high = highs[i]
        low = lows[i]

        if position == 0:
            if signal == 0:
                blocked_signal = 0
            elif signal != blocked_signal:
                # Open position
                position = signal
                entry_idx = i
                entry_price = price * (1.0 + float(position) * slippage_pct)

                if use_sl_tp:
                    if position == 1: # Long
                        sl_price = entry_price * (1.0 - sl_pct / 100.0)
                        tp_price = entry_price * (1.0 + tp_pct / 100.0)
                    else: # Short
                        sl_price = entry_price * (1.0 + sl_pct / 100.0)
                        tp_price = entry_price * (1.0 - tp_pct / 100.0)
        else:
            # Check for SL/TP first
            hit_exit = False
            exit_price = price

            if use_sl_tp:
                if position == 1: # Long
                    if low <= sl_price:
                        exit_price = sl_price
                        hit_exit = True
                    elif high >= tp_price:
                        exit_price = tp_price
                        hit_exit = True
                else: # Short
                    if high >= sl_price:
                        exit_price = sl_price
                        hit_exit = True
                    elif low <= tp_price:
                        exit_price = tp_price
                        hit_exit = True

            # Check for signal exit if SL/TP not hit
            if not hit_exit and signal == -position:
                exit_price = price
                hit_exit = True

            if hit_exit:
                # Close position
                exit_price_adj = exit_price * (1.0 - float(position) * slippage_pct)
                pnl = (exit_price_adj - entry_price) * position
                pnl_pct = (pnl / entry_price) - commission_pct * 2.0 # Round trip commission

                results.append(
                    (entry_idx, i, entry_price, exit_price, position, pnl, pnl_pct)
                )

                # Reset position and block current signal
                blocked_signal = signal
                position = 0

    return results


@njit(parallel=True)
def calculate_batch_fast(
    prices: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    signal_matrix: np.ndarray,
    use_sl_tp: bool,
    sl_pct: float,
    tp_pct: float,
    commission_pct: float = 0.0,
    slippage_pct: float = 0.0,
) -> np.ndarray:
    """Calculate basic metrics for a batch of signal sets in parallel."""
    n_indicators = signal_matrix.shape[0]
    results = np.zeros((n_indicators, 4), dtype=np.float64)  # total_return, max_dd, pf, n_trades

    for i in prange(n_indicators):
        signals = signal_matrix[i]

        # Simplified extraction for speed
        position: int = 0
        entry_price: float = 0.0
        sl_price: float = 0.0
        tp_price: float = 0.0
        blocked_signal: int = 0

        total_pnl_pct = 0.0
        gross_profit = 0.0
        gross_loss = 0.0
        n_trades = 0

        # Equity curve for drawdown
        equity = 1.0
        max_equity = 1.0
        max_dd = 0.0

        for j in range(len(signals)):
            signal = int(signals[j])
            price = prices[j]
            high = highs[j]
            low = lows[j]

            if position == 0:
                if signal == 0:
                    blocked_signal = 0
                elif signal != blocked_signal:
                    position = signal
                    entry_price = price
                    if use_sl_tp:
                        if position == 1:
                            sl_price = entry_price * (1.0 - sl_pct / 100.0)
                            tp_price = entry_price * (1.0 + tp_pct / 100.0)
                        else:
                            sl_price = entry_price * (1.0 + sl_pct / 100.0)
                            tp_price = entry_price * (1.0 - tp_pct / 100.0)
            else:
                hit_exit = False
                exit_price = price

                if use_sl_tp:
                    if position == 1:
                        if low <= sl_price:
                            exit_price = sl_price
                            hit_exit = True
                        elif high >= tp_price:
                            exit_price = tp_price
                            hit_exit = True
                    else:
                        if high >= sl_price:
                            exit_price = sl_price
                            hit_exit = True
                        elif low <= tp_price:
                            exit_price = tp_price
                            hit_exit = True

                if not hit_exit and signal == -position:
                    exit_price = price
                    hit_exit = True

                if hit_exit:
                    pnl = (exit_price - entry_price) * position
                    pnl_pct = pnl / entry_price
                    total_pnl_pct += pnl_pct

                    if pnl > 0: gross_profit += pnl
                    else: gross_loss += abs(pnl)

                    # Update equity and drawdown
                    equity *= (1.0 + pnl_pct)
                    if equity > max_equity: max_equity = equity
                    dd = (max_equity - equity) / max_equity
                    if dd > max_dd: max_dd = dd

                    blocked_signal = signal
                    position = 0
                    n_trades += 1

        pf = gross_profit / gross_loss if gross_loss > 0 else 100.0
        results[i, 0] = total_pnl_pct
        results[i, 1] = max_dd
        results[i, 2] = pf
        results[i, 3] = n_trades

    return results


@njit(parallel=True)
def calculate_batch_multi_price_fast(
    price_matrix: np.ndarray,
    high_matrix: np.ndarray,
    low_matrix: np.ndarray,
    signal_matrix: np.ndarray,
    use_sl_tp: bool,
    sl_pct: float,
    tp_pct: float,
    commission_pct: float = 0.0,
    slippage_pct: float = 0.0,
) -> np.ndarray:
    """Calculate basic metrics for a batch where each row has its own prices."""
    n_rows = signal_matrix.shape[0]
    results = np.zeros((n_rows, 4), dtype=np.float64)  # total_return, max_dd, pf, n_trades

    for i in prange(n_rows):
        signals = signal_matrix[i]
        prices = price_matrix[i]
        highs = high_matrix[i]
        lows = low_matrix[i]

        # Simplified extraction for speed
        position: int = 0
        entry_price: float = 0.0
        sl_price: float = 0.0
        tp_price: float = 0.0
        blocked_signal: int = 0

        total_pnl_pct = 0.0
        gross_profit = 0.0
        gross_loss = 0.0
        n_trades = 0

        # Equity curve for drawdown
        equity = 1.0
        max_equity = 1.0
        max_dd = 0.0

        # We need to know the actual length of this row (ignoring padding)
        # We assume non-zero prices mean actual data
        row_len = len(signals)
        while row_len > 0 and prices[row_len-1] == 0:
            row_len -= 1

        for j in range(row_len):
            signal = int(signals[j])
            price = prices[j]
            high = highs[j]
            low = lows[j]

            if position == 0:
                if signal == 0:
                    blocked_signal = 0
                elif signal != blocked_signal:
                    position = signal
                    entry_price = price
                    if use_sl_tp:
                        if position == 1:
                            sl_price = entry_price * (1.0 - sl_pct / 100.0)
                            tp_price = entry_price * (1.0 + tp_pct / 100.0)
                        else:
                            sl_price = entry_price * (1.0 + sl_pct / 100.0)
                            tp_price = entry_price * (1.0 - tp_pct / 100.0)
            else:
                hit_exit = False
                exit_price = price

                if use_sl_tp:
                    if position == 1:
                        if low <= sl_price:
                            exit_price = sl_price
                            hit_exit = True
                        elif high >= tp_price:
                            exit_price = tp_price
                            hit_exit = True
                    else:
                        if high >= sl_price:
                            exit_price = sl_price
                            hit_exit = True
                        elif low <= tp_price:
                            exit_price = tp_price
                            hit_exit = True

                if not hit_exit and signal == -position:
                    exit_price = price
                    hit_exit = True

                if hit_exit:
                    pnl = (exit_price - entry_price) * position
                    pnl_pct = pnl / entry_price
                    total_pnl_pct += pnl_pct

                    if pnl > 0: gross_profit += pnl
                    else: gross_loss += abs(pnl)

                    # Update equity and drawdown
                    equity *= (1.0 + pnl_pct)
                    if equity > max_equity: max_equity = equity
                    dd = (max_equity - equity) / max_equity
                    if dd > max_dd: max_dd = dd

                    blocked_signal = signal
                    position = 0
                    n_trades += 1

        pf = gross_profit / gross_loss if gross_loss > 0 else 100.0
        results[i, 0] = total_pnl_pct
        results[i, 1] = max_dd
        results[i, 2] = pf
        results[i, 3] = n_trades

    return results
