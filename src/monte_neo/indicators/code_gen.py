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
        # 0: Binary Op, 1: Unary/Func
        op_type = self.rng.integers(0, 2)

        if op_type == 0:
            # Binary
            # For simplicity, let's stick to arithmetic and let DynamicIndicator handle >0 logic
            # UNLESS we explicitly want boolean signals.
            # The current DynamicIndicator maps >0 to 1, <0 to -1.
            # So (Close - MA) is good.

            op = self.rng.choice(["+", "-", "*", "/"])
            left = self.generate_code(depth + 1)
            right = self.generate_code(depth + 1)
            return f"({left} {op} {right})"

        else:
            # Functions
            # rolling_mean, diff, shift

            func_type = self.rng.choice(["mean", "max", "min", "std", "diff", "shift"])
            period = self.rng.integers(3, 21)
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
                return f"{inner}.diff()"  # Default diff 1
            elif func_type == "shift":
                return f"{inner}.shift({period})"

        return "data['close']"  # Fallback
