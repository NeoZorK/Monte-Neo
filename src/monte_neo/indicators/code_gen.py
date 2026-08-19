"""Dynamic code generation module."""

from __future__ import annotations

import numpy as np


class CodeGenerator:
    """Generates random Python code for DynamicIndicator."""

    def __init__(self, rng: np.random.Generator | None = None):
        """Initialize generator.

        Args:
            rng: Random number generator.
        """
        self.rng = rng or np.random.default_rng()

    def generate_code(self, depth: int = 0) -> str:
        """Generate a random valid Python expression for an indicator."""
        # Operands
        operands = [
            "data['close']",
            "data['open']",
            "data['high']",
            "data['low']",
            "data['volume']",
        ]

        # Terminal condition (max depth or random stop)
        if depth >= 3 or (depth > 0 and self.rng.random() < 0.3):
            return self.rng.choice(operands)

        # Operators / Functions
        # 0: Binary Op, 1: Unary/Func, 2: Crossover (New)
        op_type = self.rng.integers(0, 3)

        if op_type == 0:
            # Binary
            op = self.rng.choice(["+", "-", "*", "/"])
            left = self.generate_code(depth + 1)
            right = self.generate_code(depth + 1)
            return f"({left} {op} {right})"

        elif op_type == 1:
            # Functions
            func_type = self.rng.choice(["mean", "max", "min", "std", "diff", "shift", "rsi", "bbands", "macd"])
            period = int(self.rng.integers(3, 50))
            inner = self.generate_code(depth + 1)

            if func_type == "mean":
                return f"{inner}.rolling({period}, min_periods=1).mean()"
            elif func_type == "max":
                return f"{inner}.rolling({period}, min_periods=1).max()"
            elif func_type == "min":
                return f"{inner}.rolling({period}, min_periods=1).min()"
            elif func_type == "std":
                return f"{inner}.rolling({period}, min_periods=2).std()"
            elif func_type == "diff":
                return f"{inner}.diff()"
            elif func_type == "shift":
                return f"{inner}.shift({period})"
            elif func_type == "rsi":
                return f"rsi({inner}, {period})"
            elif func_type == "bbands":
                return f"({inner} - {inner}.rolling({period}).mean()) / {inner}.rolling({period}).std()"
            elif func_type == "macd":
                fast = period
                slow = int(period * 2.2)
                return f"({inner}.ewm(span={fast}).mean() - {inner}.ewm(span={slow}).mean())"
        
        else:
            # Crossover patterns (Highly effective for signals)
            p1 = int(self.rng.integers(5, 30))
            p2 = int(self.rng.integers(p1 + 5, p1 + 50))
            return f"(data['close'].rolling({p1}).mean() - data['close'].rolling({p2}).mean())"

        return "data['close']"  # Fallback
