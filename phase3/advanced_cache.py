#!/usr/bin/env python3
"""
Advanced Caching System for Local AI Models
LRU Memory + Semantic Similarity + Disk Persistence
100% LOCAL - NO CLOUD
"""

import sqlite3
import hashlib
import time
from typing import Dict, Any, Optional, List, Tuple
from collections import OrderedDict
from pathlib import Path
import json
import logging


class LRUCache:
    """In-memory LRU cache for super-fast responses"""

    def __init__(self, max_size: int = 1000):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        self.logger = logging.getLogger("LRUCache")

    def get(self, key: str) -> Optional[str]:
        """Get from cache (O(1))"""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None

    def put(self, key: str, value: str):
        """Put in cache with LRU eviction"""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value

        # Evict oldest if over capacity
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "total_requests": total
        }


class SemanticCache:
    """Semantic similarity caching using embeddings"""

    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold
        self.cache = {}
        self.embeddings = {}
        self.logger = logging.getLogger("SemanticCache")

        # Load embedding model (all-MiniLM-L6-v2 - 22MB)
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.logger.info("✅ Semantic cache initialized (all-MiniLM-L6-v2)")
        except ImportError:
            self.logger.warning("sentence-transformers not installed - semantic cache disabled")
            self.model = None

    def find_similar(self, prompt: str) -> Optional[str]:
        """Find semantically similar cached response"""
        if not self.model:
            return None

        # Get embedding for prompt
        prompt_embedding = self.model.encode(prompt)

        # Search for similar in cache
        best_match = None
        best_similarity = 0

        for cached_prompt, cached_response in self.cache.items():
            cached_embedding = self.embeddings[cached_prompt]
            similarity = self._cosine_similarity(prompt_embedding, cached_embedding)

            if similarity > self.threshold and similarity > best_similarity:
                best_match = cached_response
                best_similarity = similarity

        if best_match:
            self.logger.debug(f"Semantic match found: {best_similarity:.2f} similarity")
            return best_match

        return None

    def cache_response(self, prompt: str, response: str):
        """Cache response with embedding"""
        if not self.model:
            return

        embedding = self.model.encode(prompt)
        self.embeddings[prompt] = embedding
        self.cache[prompt] = response

    def _cosine_similarity(self, a, b) -> float:
        """Calculate cosine similarity between embeddings"""
        import numpy as np
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class DiskCache:
    """Persistent disk-based cache using SQLite"""

    def __init__(self, db_path: str = "response_cache.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("DiskCache")

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                id INTEGER PRIMARY KEY,
                prompt_hash TEXT UNIQUE,
                prompt TEXT,
                response TEXT,
                model TEXT,
                timestamp REAL,
                hits INTEGER DEFAULT 0
            )
        """)

        conn.commit()
        conn.close()
        self.logger.info(f"✅ Disk cache initialized: {self.db_path}")

    def get(self, prompt: str) -> Optional[str]:
        """Get from disk cache"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT response FROM cache
            WHERE prompt_hash = ?
        """, (prompt_hash,))

        result = cursor.fetchone()

        if result:
            # Increment hits
            cursor.execute("""
                UPDATE cache SET hits = hits + 1
                WHERE prompt_hash = ?
            """, (prompt_hash,))
            conn.commit()
            self.logger.debug(f"Disk cache hit: {prompt_hash}")

        conn.close()
        return result[0] if result else None

    def put(self, prompt: str, response: str, model: str):
        """Put in disk cache"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO cache
            (prompt_hash, prompt, response, model, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (prompt_hash, prompt, response, model, time.time()))

        conn.commit()
        conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get disk cache statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM cache")
        total_entries = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(hits) FROM cache")
        total_hits = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(DISTINCT model) FROM cache")
        models = cursor.fetchone()[0]

        conn.close()

        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "distinct_models": models,
            "db_file": self.db_path
        }


class SmartCache:
    """Unified smart caching system"""

    def __init__(self, lru_size: int = 1000):
        self.memory_cache = LRUCache(max_size=lru_size)
        self.semantic_cache = SemanticCache()
        self.disk_cache = DiskCache()
        self.logger = logging.getLogger("SmartCache")

    def get_or_compute(self, prompt: str, compute_fn, model: str = "default"):
        """Get from cache or compute"""
        # 1. Exact match in memory (super fast <1ms)
        exact_key = hashlib.md5(prompt.encode()).hexdigest()
        memory_result = self.memory_cache.get(exact_key)
        if memory_result:
            self.logger.debug("✅ Memory cache hit")
            return memory_result

        # 2. Semantic match (fast ~10ms)
        semantic_result = self.semantic_cache.find_similar(prompt)
        if semantic_result:
            self.logger.debug("✅ Semantic cache hit")
            self.memory_cache.put(exact_key, semantic_result)
            return semantic_result

        # 3. Disk cache (slower ~100ms)
        disk_result = self.disk_cache.get(prompt)
        if disk_result:
            self.logger.debug("✅ Disk cache hit")
            self.memory_cache.put(exact_key, disk_result)
            self.semantic_cache.cache_response(prompt, disk_result)
            return disk_result

        # 4. Compute new response (slow ~1-10s)
        self.logger.debug("💻 Computing new response...")
        result = compute_fn()

        # Cache everywhere
        self.memory_cache.put(exact_key, result)
        self.semantic_cache.cache_response(prompt, result)
        self.disk_cache.put(prompt, result, model)

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return {
            "memory": self.memory_cache.get_stats(),
            "disk": self.disk_cache.get_stats(),
            "semantic_threshold": self.semantic_cache.threshold
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n🧪 ADVANCED CACHE TESTING")
    print("=" * 60)

    cache = SmartCache()

    # Simulate queries
    prompts = [
        "What is machine learning?",
        "What is machine learning?",  # Exact duplicate
        "What is ML?",  # Semantic match
        "Explain artificial intelligence",
    ]

    for i, prompt in enumerate(prompts, 1):
        print(f"\nQuery {i}: {prompt}")
        result = cache.get_or_compute(
            prompt,
            compute_fn=lambda: f"Response to: {prompt}",
            model="test"
        )
        print(f"Result: {result[:50]}...")

    # Print statistics
    print("\n" + "=" * 60)
    print("📊 CACHE STATISTICS:")
    print("=" * 60)
    stats = cache.get_stats()
    print(json.dumps(stats, indent=2))
