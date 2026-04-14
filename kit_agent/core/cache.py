import hashlib
import time


class SemanticCache:
    def __init__(self, ttl: int = 86400):
        self.store: dict[str, dict] = {}
        self.ttl = ttl  # Patch 1: 24h default

    def _generate_key(self, task: str, context_hash: str) -> str:
        """Key depends on task AND context state hash"""
        combined = f"{task}:{context_hash}"
        return hashlib.md5(combined.encode()).hexdigest()

    def get(self, task: str, context_hash: str) -> str | None:
        """
        Patch 1: Staleness control
        """
        key = self._generate_key(task, context_hash)
        entry = self.store.get(key)

        if not entry:
            return None

        # Check TTL
        if (time.time() - entry["timestamp"]) > self.ttl:
            del self.store[key]
            return None

        # Check Confidence (from .kit's perspective)
        if entry["score"] < 0.9:
            return None

        return entry["result"]

    def set(self, task: str, context_hash: str, result: str, score: float = 1.0):
        key = self._generate_key(task, context_hash)
        self.store[key] = {"result": result, "score": score, "timestamp": time.time()}
