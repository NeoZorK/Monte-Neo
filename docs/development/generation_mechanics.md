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

## 3. Monte Carlo Validation Workflow

Once a candidate indicator is evolved and passes basic backtesting, it enters the **Monte Carlo Validation** phase:

### Parallel Execution (GPU/Numba)
- **MLX Engine**: For large-scale testing, scenarios are offloaded to the GPU.
- **Numba Parallelism**: Metrics calculations for SL/TP and scenarios are processed in parallel using JIT-compiled code, reaching 300k+ operations per second.

### Sequential Mode (Optimized Workflow)
To maximize efficiency, validation can run in **Sequential Mode**:
1.  **Step-by-Step**: Each Monte Carlo method (Walk-Forward, Shuffling, etc.) is executed one after another.
2.  **Early Termination**: If an indicator fails to pass the **Pass Threshold** (e.g., 95%) in any single method, the entire validation for that candidate is aborted. This prevents wasting CPU/GPU time on candidates that are already proven non-robust.

---

## 4. Global Leadership Pipeline & Smart Search

The **Global Leadership Pipeline** is the most advanced orchestration layer in Monte-Neo. It automates the entire lifecycle of an indicator, from initial evolution to production certification.

### Iterative Smart Search
Unlike a standard generation run, the Global Leadership Pipeline operates in a "Smart Search" loop. If a candidate indicator is evolved but then **REJECTED** by the Production Gate (due to overfitting, low trade count, or poor OOS performance), the system doesn't stop. Instead, it triggers the **SmartPipelineOptimizer**:

1.  **Failure Analysis**: The optimizer analyzes the validation report to identify *why* the indicator failed.
2.  **Adaptive Parameter Tuning**: 
    - **Overfitting detected**: The system automatically decreases `mutation_rate` and increases `crossover_rate` to favor stable, proven genetic combinations over risky new mutations.
    - **Low Trade Count**: It increases `population_size` to broaden the search space and find more active entry/exit conditions.
    - **Low Quality/Fitness**: It increases the number of `generations` to allow the evolution more time to converge on a superior solution.
3.  **Brainstorm Reporting**: Before each new iteration, the system provides a "Brainstorm Report" in the console, detailing the best score achieved so far, the identified failure reason, and the specific adjustments made to the search parameters.

### Loop Persistence
The pipeline continues this iterative process—evolving, validating, and adjusting—until one of two conditions is met:
-   An **ACCEPTED** indicator is found and certified for production.
-   The user manually interrupts the process (Ctrl+C).

---

## 5. Workflow Summary

1.  **Generator** creates a string: `"(data['close'] - data['close'].rolling(14).mean())"`
2.  **DynamicIndicator** compiles it into a Python function.
3.  **Backtester** feeds OHLCV data into the function.
4.  **Signals** are generated based on the numeric output.
5.  **Metrics** are calculated and fed back to the Generator to evolve better versions.
