# Dynamic Indicator Generation

Monte-Neo supports dynamic generation of trading indicators. Instead of relying solely on pre-defined indicators (like RSI, SMA), the system can generate novel indicators by composing mathematical operations and transformations on raw market data.

## Concept

The core idea is to treat an indicator as a formula or a "gene" that transforms input data (OHLCV) into a signal.
We use a genetic programming approach where:
1.  **Genes** are random valid Python expressions.
2.  **Fitness** is determined by the indicator's performance metrics (Profit Factor, Sharpe, etc.) and robustness (Monte Carlo validation).

## Structure of a Dynamic Indicator

A dynamic indicator is defined by a **Source Code String**. This string is a valid Python expression that can be evaluated using `pandas` and `numpy`.

### Available Operands
- `open`, `high`, `low`, `close`, `volume` (from the input DataFrame).

### Available Operators
- Arithmetic: `+`, `-`, `*`, `/`
- Comparison: `>`, `<`, `==` (for signals)

### Available Functions
- `abs(x)`
- `log(x)` (numpy)
- `sqrt(x)` (numpy)
- `shift(x, n)`
- `diff(x)`
- `rolling_mean(x, window)`
- `rolling_max(x, window)`
- `rolling_min(x, window)`
- `rolling_std(x, window)`

## Example Generated Indicators

```python
# Simple momentum
(close - shift(close, 10)) > 0

# Volatility breakout
close > (rolling_mean(close, 20) + 2 * rolling_std(close, 20))

# Complex random generation
(rolling_mean(close, 14) / shift(close, 5)) - 1
```

## Security Implementation

The system uses `exec()` or `eval()` to run these generated strings. To mitigate security risks:
- The scope passed to `eval()` is strictly limited to allowed data and safe functions.
- No access to `os`, `sys`, or other system modules is provided.
