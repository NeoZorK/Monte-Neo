# Dynamic Indicator Generation

Monte-Neo supports dynamic generation of trading indicators. Instead of relying solely on pre-defined indicators (like RSI, SMA), the system can generate novel indicators by composing mathematical operations and transformations on raw market data.

## Concept

The core idea is to treat an indicator as a formula or a "gene" that transforms input data (OHLCV) into a signal.
We use a genetic programming approach where:
1.  **Genes** are random valid Python expressions.
10: 2.  **Fitness** is determined by the indicator's performance metrics (Profit Factor, Sharpe, etc.) and robustness (Monte Carlo validation).
11: 
12: ## How it Works
13: 
14: The dynamic generation process follows three main steps:
15: 
16: ### 1. Code Generation ("Genetics")
17: The system randomly constructs a Python code string, similar to building with LEGO blocks. The components include:
18: *   **Data**: `close`, `open`, `volume`, etc.
19: *   **Math**: arithmetic operators (`+`, `-`, `*`, `/`).
20: *   **Functions**: `rolling_mean`, `shift`, `diff`, etc.
21: 
22: *Example generated code:*
23: ```python
24: (data['close'] - data['close'].rolling(20).mean()) / data['volume']
25: ```
26: 
27: ### 2. Safe Compilation
28: The `DynamicIndicator` class takes this valid Python string and compiles it within a restricted environment. For security, it only has access to specific data arrays and mathematical functions, ensuring it cannot impact the host system.
29: 
30: ### 3. Evaluation & Optimization
31: Once compiled, the indicator is treated like any standard indicator:
32: *   **Signal Generation**: It produces buy/sell signals.
33: *   **Backtesting**: Performance metrics are calculated.
34: *   **Monte Carlo**: Robustness is verified against noise and shuffling.
35: 
36: If the generated indicator passes all tests, it is saved as a viable strategy candidate.
37: 
38: ## Structure of a Dynamic Indicator

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

## Evolutionary Optimization

To find the best strategies, the system uses **Genetic Programming**:

1.  **Selection**: Indicators with the highest "Survival Score" (based on Profit, Drawdown, and Monte Carlo robustness) are chosen as parents.
2.  **Mutation**: Random parts of the formula are changed.
    *   *Example*: `mean(close, 20)` -> `mean(close, 50)`
    *   *Example*: `close - open` -> `close * open`
3.  **Crossover**: Parts of two logical parents are swapped to create a child.
    *   *Parent A*: `RSI(14)`
    *   *Parent B*: `SMA(50)`
    *   *Child*: `RSI(14) > SMA(50)`

This process runs for multiple generations, constantly refining the population towards robust profitability.
