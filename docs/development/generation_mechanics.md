# Generation Mechanics: Deep Dive

This document provides a technical explanation of how the **Indicator Generator** and **Dynamic Indicators** work within Monte-Neo.

---

## 1. Indicator Generator (`generator.py`)

The `IndicatorGenerator` is responsible for searching the "strategy space" to find robust trading rules.

### Recursive Expression Building
The core of dynamic generation is the `_generate_dynamic_code` method. It uses a recursive approach to build valid Python/Pandas expressions:

- **Depth Control**: To prevent overly complex or infinite expressions, it uses a `depth` parameter. At `depth >= 3`, it forces the selection of a terminal operand (like `data['close']`).
- **Weighted Selection**: It randomly chooses between:
    - **Binary Operations**: `(left_expr + right_expr)`, where `left` and `right` are generated recursively.
    - **Functional Operations**: Applies transformations like `.rolling(n).mean()`, `.diff()`, or `.shift(n)`.
- **Variety**: By combining these, it can generate anything from a simple price-action rule to complex volatility-adjusted momentum indicators.

### The Evolutionary Loop
Instead of just random guessing, the generator uses **Genetic Programming**:

1.  **Initial Population**: Generates a set of random indicators.
2.  **Fitness Evaluation**: Each indicator is backtested. The "Fitness Score" is a composite of:
    - `Profit Factor` (How much it makes vs. loses)
    - `Max Drawdown` (Risk)
    - `Trade Count` (Statistical significance)
3.  **Selection**: Uses **Tournament Selection** (picking a few random candidates and taking the best) to choose parents for the next generation.
4.  **Mutation**:
    - **Parameter Mutation**: Uses regex to find numbers in the code string and perturb them (e.g., changing `rolling(20)` to `rolling(22)`).
    - **Structural Mutation**: Wraps an existing expression in a new operation (e.g., `(expr) / data['volume']`).

---

## 2. Dynamic Indicators (`dynamic.py`)

The `DynamicIndicator` class acts as a "shell" that can execute any valid Python expression as a trading strategy.

### Safe Runtime Execution
Executing strings as code is powerful but dangerous. Monte-Neo handles this using "Restricted Compilation":

```python
# Internal logic simplified
func_code = f"def _dynamic_calc(data, np, pd):\n    return {self.source_code}"
local_scope = {}
exec(func_code, {}, local_scope)
self._compiled_code = local_scope["_dynamic_calc"]
```

- **Isolation**: The code is compiled into a function that only accepts `data`, `np`, and `pd`. It doesn't have access to `os`, `sys`, or the global state of the application.
- **Caching**: The compilation happens only once per indicator instance to ensure performance during backtesting and Monte Carlo simulations.

### Signal Interpretation
Since the generated code can return anything, the `DynamicIndicator` applies a standardized interpretation layer:

1.  **Boolean Signals**: If the expression returns `True/False` (e.g., `close > sma`), it maps `True` to a **Buy (1)** signal.
2.  **Numeric Signals**: If it returns a value (e.g., a momentum oscillator), it uses the zero-cross logic:
    - `Value > 0`  → **Buy (1)**
    - `Value < 0`  → **Sell (-1)**
    - `Value == 0` → **Hold (0)**
3.  **Data Alignment**: It automatically ensures the output matches the input data's index, handling the "look-ahead bias" by relying on Pandas' native `shift` and `rolling` methods.

---

## 3. Workflow Summary

1.  **Generator** creates a string: `"(data['close'] - data['close'].rolling(14).mean())"`
2.  **DynamicIndicator** compiles it into a Python function.
3.  **Backtester** feeds OHLCV data into the function.
4.  **Signals** are generated based on the numeric output.
5.  **Metrics** are calculated and fed back to the Generator to evolve better versions.
