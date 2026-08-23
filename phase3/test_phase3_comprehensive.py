#!/usr/bin/env python3
"""
Comprehensive Test Suite for Phase 3 Components
Tests all components: cache, ensemble, monitoring, adapters
"""

import unittest
import tempfile
import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import components to test
try:
    from advanced_cache import SmartCache, LRUCache, DiskCache, SemanticCache
    from ensemble import LocalEnsemble
    from monitoring import LLMMetrics, QueryTracer
    from opencode_adapter import CodeAnalyzer, CodeCompletion, TestGenerator
    from cline_adapter import FileOperations, CommandExecutor, TaskExecutor
except ImportError as e:
    print(f"⚠️ Import warning: {e}")


class TestLRUCache(unittest.TestCase):
    """Test LRU cache implementation"""

    def setUp(self):
        self.cache = LRUCache(max_size=3)

    def test_put_and_get(self):
        """Test basic put/get"""
        self.cache.put("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")

    def test_lru_eviction(self):
        """Test LRU eviction when over capacity"""
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        self.cache.put("key3", "value3")
        self.cache.put("key4", "value4")  # Should evict key1

        self.assertIsNone(self.cache.get("key1"))
        self.assertEqual(self.cache.get("key4"), "value4")

    def test_cache_stats(self):
        """Test cache statistics"""
        self.cache.put("key1", "value1")
        self.cache.get("key1")  # Hit
        self.cache.get("key2")  # Miss

        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertIn("hit_rate", stats)


class TestDiskCache(unittest.TestCase):
    """Test disk cache implementation"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cache.db"
        self.cache = DiskCache(str(self.db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_put_and_get(self):
        """Test disk cache put/get"""
        self.cache.put("test_prompt", "test_response", "test_model")
        result = self.cache.get("test_prompt")
        self.assertEqual(result, "test_response")

    def test_cache_stats(self):
        """Test disk cache statistics"""
        self.cache.put("prompt1", "response1", "model1")
        self.cache.put("prompt2", "response2", "model1")

        stats = self.cache.get_stats()
        self.assertEqual(stats["total_entries"], 2)
        self.assertEqual(stats["distinct_models"], 1)


class TestSmartCache(unittest.TestCase):
    """Test unified smart cache"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache = SmartCache()
        self.compute_count = 0

    def tearDown(self):
        self.temp_dir.cleanup()

    def compute_fn(self):
        """Mock compute function"""
        self.compute_count += 1
        return "computed_result"

    def test_memory_cache_first(self):
        """Test memory cache is checked first"""
        result = self.cache.get_or_compute(
            "test_prompt",
            self.compute_fn,
            "test_model"
        )

        self.assertEqual(result, "computed_result")
        self.assertEqual(self.compute_count, 1)

        # Second call should hit memory cache
        result = self.cache.get_or_compute(
            "test_prompt",
            self.compute_fn,
            "test_model"
        )

        self.assertEqual(self.compute_count, 1)  # No new computation

    def test_cache_stats(self):
        """Test cache statistics"""
        self.cache.get_or_compute("prompt1", self.compute_fn, "model")
        stats = self.cache.get_stats()

        self.assertIn("memory", stats)
        self.assertIn("disk", stats)


class TestEnsemble(unittest.TestCase):
    """Test ensemble voting system"""

    def setUp(self):
        self.mock_client = Mock()
        self.ensemble = LocalEnsemble(self.mock_client, "balanced")

    def test_ensemble_initialization(self):
        """Test ensemble initializes correctly"""
        self.assertEqual(self.ensemble.mode, "balanced")
        self.assertEqual(len(self.ensemble.models), 2)

    def test_ensemble_modes(self):
        """Test all ensemble modes"""
        for mode in ["quality", "balanced", "speed"]:
            ensemble = LocalEnsemble(self.mock_client, mode)
            self.assertEqual(ensemble.mode, mode)
            self.assertGreater(len(ensemble.models), 0)

    def test_confidence_calculation(self):
        """Test confidence scoring"""
        response = {
            "model": "qwen3:8b",
            "response": "This is a detailed response with examples and code.",
            "speed_tps": 25
        }

        score = self.ensemble._calculate_confidence(response)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1.0)


class TestMetrics(unittest.TestCase):
    """Test monitoring metrics"""

    def setUp(self):
        self.metrics = LLMMetrics()

    def test_record_query(self):
        """Test recording query metrics"""
        self.metrics.record_query(
            model="qwen3:8b",
            provider="local",
            duration=1.5,
            tokens_input=50,
            tokens_output=100,
            cost_usd=0.0,
            cached=False
        )

        # Verify metrics were recorded
        self.assertGreater(self.metrics.queries_total.labels(
            model="qwen3:8b",
            provider="local",
            status="live"
        )._value.get(), 0)

    def test_query_tracer(self):
        """Test query tracer context manager"""
        with QueryTracer(self.metrics, "test_model", "local") as tracer:
            tracer.tokens_input = 50
            tracer.tokens_output = 100

        # Tracer should have recorded metrics
        self.assertGreater(self.metrics.queries_total.labels(
            model="test_model",
            provider="local",
            status="live"
        )._value.get(), 0)


class TestCodeAnalyzer(unittest.TestCase):
    """Test code analysis"""

    def setUp(self):
        self.mock_client = Mock()
        self.analyzer = CodeAnalyzer(self.mock_client)

    def test_analyze_code(self):
        """Test code analysis"""
        self.mock_client.query.return_value = {
            "success": True,
            "output": json.dumps({
                "bugs": ["missing error handling"],
                "security": [],
                "performance": ["inefficient loop"],
                "style": []
            })
        }

        code = "for i in range(1000000): print(i)"
        result = self.analyzer.analyze_code(code, "python")

        self.assertTrue(result["success"])
        self.assertIn("analysis", result)

    def test_suggest_refactoring(self):
        """Test refactoring suggestions"""
        self.mock_client.query.return_value = {
            "success": True,
            "output": json.dumps({
                "suggestions": ["Extract function", "Reduce complexity"],
                "examples": []
            })
        }

        code = "def complex_function(): pass"
        result = self.analyzer.suggest_refactoring(code, "python")

        self.assertTrue(result["success"])
        self.assertIn("suggestions", result)


class TestCodeCompletion(unittest.TestCase):
    """Test code completion"""

    def setUp(self):
        self.mock_client = Mock()
        self.completion = CodeCompletion(self.mock_client)

    def test_complete_code(self):
        """Test code completion"""
        self.mock_client.query.return_value = {
            "success": True,
            "output": json.dumps({
                "completions": ["result = a + b", "result = sum([a, b])"],
                "confidence": [0.95, 0.85]
            })
        }

        prefix = "def add(a, b):\n    result ="
        result = self.completion.complete_code(prefix, "python")

        self.assertTrue(result["success"])
        self.assertIn("completions", result)


class TestTestGenerator(unittest.TestCase):
    """Test test generation"""

    def setUp(self):
        self.mock_client = Mock()
        self.generator = TestGenerator(self.mock_client)

    def test_generate_tests(self):
        """Test unit test generation"""
        self.mock_client.query.return_value = {
            "success": True,
            "output": "def test_example(): assert True"
        }

        code = "def example(): return True"
        result = self.generator.generate_tests(code, "python", "pytest")

        self.assertTrue(result["success"])
        self.assertIn("tests", result)

    def test_generate_integration_tests(self):
        """Test integration test generation"""
        self.mock_client.query.return_value = {
            "success": True,
            "output": "def test_integration(): pass"
        }

        code = "def module_function(): pass"
        result = self.generator.generate_integration_tests(code, "python")

        self.assertTrue(result["success"])
        self.assertIn("tests", result)


class TestFileOperations(unittest.TestCase):
    """Test file operations"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_client = Mock()
        self.file_ops = FileOperations(self.mock_client, self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_write_and_read_file(self):
        """Test write and read file"""
        content = "test content"
        self.file_ops.write_file("test.txt", content, overwrite=True)

        result = self.file_ops.read_file("test.txt")
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], content)

    def test_list_files(self):
        """Test listing files"""
        self.file_ops.write_file("file1.txt", "content1", overwrite=True)
        self.file_ops.write_file("file2.txt", "content2", overwrite=True)

        result = self.file_ops.list_files(".", "*.txt")
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)

    def test_delete_file(self):
        """Test file deletion"""
        self.file_ops.write_file("test.txt", "content", overwrite=True)
        result = self.file_ops.delete_file("test.txt")

        self.assertTrue(result["success"])

        # Verify file is gone
        result = self.file_ops.read_file("test.txt")
        self.assertFalse(result["success"])


class TestCommandExecutor(unittest.TestCase):
    """Test command execution"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_client = Mock()
        self.executor = CommandExecutor(self.mock_client, self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_execute_command(self):
        """Test command execution"""
        result = self.executor.execute("echo 'test'")

        self.assertTrue(result["success"])
        self.assertIn("test", result["stdout"])

    def test_execute_failed_command(self):
        """Test failed command"""
        result = self.executor.execute("false")

        self.assertFalse(result["success"])
        self.assertNotEqual(result["returncode"], 0)


class TestTaskExecutor(unittest.TestCase):
    """Test task execution"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_client = Mock()
        self.executor = TaskExecutor(self.mock_client, self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_execute_task(self):
        """Test multi-step task execution"""
        self.mock_client.query.return_value = {
            "success": True,
            "output": "Step completed successfully"
        }

        task = "Create a Python module"
        steps = ["Step 1: Define class", "Step 2: Add methods"]

        result = self.executor.execute_task(task, steps)

        self.assertTrue(result["success"])
        self.assertEqual(result["steps_completed"], 2)


class TestIntegration(unittest.TestCase):
    """Integration tests for all components"""

    def setUp(self):
        self.mock_client = Mock()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_workflow(self):
        """Test complete workflow"""
        # Setup mock responses
        self.mock_client.query.return_value = {
            "success": True,
            "output": "Mock response"
        }

        # Create components
        cache = SmartCache()
        ensemble = LocalEnsemble(self.mock_client, "balanced")
        file_ops = FileOperations(self.mock_client, self.temp_dir.name)

        # Test workflow
        cache.get_or_compute("test", lambda: "result", "model")
        file_ops.write_file("test.txt", "content", overwrite=True)

        # Verify all components work
        self.assertIsNotNone(cache)
        self.assertIsNotNone(ensemble)
        self.assertIsNotNone(file_ops)


def run_tests():
    """Run all tests"""
    logging.basicConfig(level=logging.WARNING)

    print("\n" + "=" * 70)
    print("🧪 PHASE 3 COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLRUCache))
    suite.addTests(loader.loadTestsFromTestCase(TestDiskCache))
    suite.addTests(loader.loadTestsFromTestCase(TestSmartCache))
    suite.addTests(loader.loadTestsFromTestCase(TestEnsemble))
    suite.addTests(loader.loadTestsFromTestCase(TestMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestCodeAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestCodeCompletion))
    suite.addTests(loader.loadTestsFromTestCase(TestTestGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestFileOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestCommandExecutor))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskExecutor))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70 + "\n")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
