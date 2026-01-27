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

### Available Functions (Pandas/Numpy-native)
- `Series.shift(n)`
- `Series.diff()`
- `Series.rolling(window).mean()`
- `Series.rolling(window).std()`
- `Series.rolling(window).max()`
- `Series.rolling(window).min()`
- `np.log(x)`
- `np.sqrt(x)`

## Example Generated Indicators

```python
# Simple momentum
(close - shift(close, 10)) > 0

# Volatility breakout
close > (rolling_mean(close, 20) + 2 * rolling_std(close, 20))

# Complex random generation
(rolling_mean(close, 14) / shift(close, 5)) - 1
```

## Secure Compilation & Fallback

- Generated expressions are compiled into a small wrapper function via `exec()`:
  - Signature: `_dynamic_calc(data, np, pd)`
  - Scope is restricted to `data` (OHLCV DataFrame), `numpy`, and `pandas`
- If compilation fails (e.g., invalid syntax), the indicator automatically falls back to a safe expression (`data['close']`) and recompiles.
- At runtime, if evaluation fails (e.g., calling a method without parentheses), the indicator retries with the safe expression to avoid interrupting the search/evolution loop.

## Evolutionary Optimization

To find the best strategies, the system uses **Genetic Programming**:

1.  **Generation**: The system collects promising candidates from initial random search.
2.  **Evolution**: If enough candidates are found, it starts an evolutionary loop:
    - **Selection**: Indicators with the highest "Survival Score" (based on Profit, Drawdown, and Monte Carlo robustness) are chosen as parents.
    - **Mutation**: Random parts of the formula are changed or wrapped in new operations.
    - **Crossover**: AST‑based subtree swap between parent code strings.
3.  **Final Validation**: The best evolved individual undergoes a final strict Monte Carlo validation before being presented as the winner.

This process runs for multiple generations, constantly refining the population towards robust profitability.

## Performance & High-Speed Execution

To support the v0.0.3 goal of >300,000 operations per second, the `DynamicIndicator` implementation includes several performance-critical optimizations:

1. **Lightweight Data Injection**: Instead of passing full DataFrames to the evaluation engine, we use a dictionary of Pandas Series. This avoids the significant overhead of DataFrame creation and slicing during each search iteration.
2. **Fast Signal Generation**: The `generate_signals_fast` method bypasses standard Pandas indexing where possible and uses direct NumPy boolean masks for signal generation.
3. **Overflow Protection**: During high-speed casting to `float32` (required for GPU/Numba compatibility), we use `np.greater` and `np.less` to handle large values (up to 1e40+) without triggering `RuntimeWarning` overflow errors.
4. **Lazy Compilation**: Indicators are compiled once and cached for the duration of the search/evolution loop.
5. **GPU Batch Integration**: Optimized signals are returned as `float32` arrays, ready for direct offloading to the MLX GPU engine without further conversion overhead.
