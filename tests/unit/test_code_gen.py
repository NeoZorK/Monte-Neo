import unittest
from unittest.mock import MagicMock

from monte_neo.indicators.code_gen import CodeGenerator


class TestCodeGenerator(unittest.TestCase):
    def setUp(self):
        # Create a mock RNG that behaves like np.random.Generator
        self.rng = MagicMock()
        # Configure default behavior to avoid comparison errors
        self.rng.random.return_value = 0.5
        self.rng.integers.return_value = 0
        self.rng.choice.side_effect = lambda x: x[0] if isinstance(x, list) else x
        self.generator = CodeGenerator(self.rng)

    def test_init(self):
        gen = CodeGenerator()
        self.assertIsNotNone(gen.rng)

    def test_generate_code_depth_limit(self):
        # Test that depth limit is respected
        # Mock random to return 0.5 (> 0.3) to NOT stop early,
        # but depth=3 should trigger terminal condition.
        self.rng.random.return_value = 0.5
        code = self.generator.generate_code(depth=3)
        self.assertTrue(any(op in code for op in ["data['close']", "data['open']", "data['high']", "data['low']", "data['volume']"]))

    def test_generate_code_structure(self):
        # Test that it generates something
        self.rng.random.return_value = 0.5
        self.rng.integers.return_value = 0
        code = self.generator.generate_code()
        self.assertIsInstance(code, str)
        self.assertTrue(len(code) > 0)

    def test_generate_all_func_types(self):
        # Force all types to be covered
        func_types = ["mean", "max", "min", "std", "diff", "shift", "rsi", "bbands", "macd"]
        
        for f_type in func_types:
            self.rng.choice.side_effect = lambda x, f=f_type: f if isinstance(x, list) and "mean" in x else x[0]
            self.rng.integers.return_value = 1 # Force op_type=1 (Func)
            code = self.generator.generate_code()
            if f_type == "mean": self.assertIn(".rolling", code); self.assertIn(".mean()", code)
            elif f_type == "max": self.assertIn(".rolling", code); self.assertIn(".max()", code)
            elif f_type == "min": self.assertIn(".rolling", code); self.assertIn(".min()", code)
            elif f_type == "std": self.assertIn(".rolling", code); self.assertIn(".std()", code)
            elif f_type == "diff": self.assertIn(".diff()", code)
            elif f_type == "shift": self.assertIn(".shift", code)
            elif f_type == "rsi": self.assertIn("rsi(", code)
            elif f_type == "bbands": self.assertIn("rolling", code); self.assertIn("std()", code)
            elif f_type == "macd": self.assertIn("ewm(span=", code)

    def test_binary_ops(self):
        # Force binary op (op_type=0)
        self.rng.integers.return_value = 0
        self.rng.choice.side_effect = lambda x: "+" if isinstance(x, list) and "+" in x else x[0]
        code = self.generator.generate_code()
        self.assertIn(" + ", code)
        self.assertTrue(code.startswith("("))
        self.assertTrue(code.endswith(")"))

    def test_fallback_coverage(self):
        # Trigger the final fallback line 79
        # Mock op_type=1 (else block) but func_type to something unknown
        self.rng.integers.return_value = 1
        self.rng.choice.side_effect = lambda x: "unknown_func" if isinstance(x, list) and "mean" in x else x[0]
        code = self.generator.generate_code()
        self.assertEqual(code, "data['close']")

if __name__ == "__main__":
    unittest.main()
