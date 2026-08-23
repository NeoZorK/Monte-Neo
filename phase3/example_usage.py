#!/usr/bin/env python3
"""
Phase 3 Integration Example
Shows how to use Phase 3 components in your project
"""

import logging
from ensemble import LocalEnsemble
from advanced_cache import SmartCache
from opencode_adapter import CodeAnalyzer, CodeCompletion
from cline_adapter import FileOperations, CommandExecutor
from local_ai_wrapper import UnifiedModelClient

logging.basicConfig(level=logging.INFO)

# Setup client
client = UnifiedModelClient()

# Example 1: Ensemble voting
print("\n1️⃣  ENSEMBLE VOTING")
print("-" * 40)
ensemble = LocalEnsemble(client, "balanced")
result = ensemble.query_ensemble("What is machine learning?")
print(f"Response: {result['response'][:100]}...")
print(f"Confidence: {result['confidence']:.2f}")

# Example 2: Smart caching
print("\n2️⃣  SMART CACHING")
print("-" * 40)
cache = SmartCache()

def compute():
    return client.query("qwen3:8b", "Explain AI").get("output", "")

result = cache.get_or_compute("Explain AI", compute, "qwen3:8b")
print(f"Result: {result[:80]}...")

# Example 3: Code analysis
print("\n3️⃣  CODE ANALYSIS")
print("-" * 40)
analyzer = CodeAnalyzer(client)
code = """
def slow_function(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
analysis = analyzer.suggest_refactoring(code, "python")
print(f"Suggestions: {analysis.get('suggestions', {})}")

# Example 4: File operations
print("\n4️⃣  AUTONOMOUS TASK EXECUTION")
print("-" * 40)
file_ops = FileOperations(client, ".")
file_ops.write_file("example.txt", "Phase 3 is awesome!", overwrite=True)
content = file_ops.read_file("example.txt")
print(f"File content: {content.get('content', 'N/A')}")

print("\n✅ All Phase 3 components working!")
