# kit/analysis/integrity.py
import time
from pathlib import Path
from typing import Any, Dict

from kit.core.graph_store import GraphStore


class ArchitectureDoctor:
    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def get_health_metrics(self, root_path: str) -> Dict[str, Any]:
        """Gather all architectural health metrics as a dictionary."""
        # 1. FS Latency Check
        fs_time = self._check_fs_latency(root_path)

        # 2. Entity Statistics
        cur = self.store.conn.cursor()

        # Count symbols by kind
        rows = cur.execute(
            "SELECT kind, COUNT(*) FROM symbols GROUP BY kind"
        ).fetchall()
        entities: Dict[str, int] = {kind: count for kind, count in rows}
        total_symbols = sum(entities.values())

        # Count documents
        doc_count = entities.get("document", 0)
        code_symbols = total_symbols - doc_count

        # 3. Layer Statistics
        edges_stats = cur.execute(
            "SELECT layer, COUNT(*) FROM edges GROUP BY layer"
        ).fetchall()
        layers: Dict[str, int] = {f"layer_{l}": c for l, c in edges_stats}

        return {
            "fs_latency_ms": fs_time,
            "total_symbols": total_symbols,
            "code_symbols": code_symbols,
            "document_symbols": doc_count,
            "entities": entities,
            "layers": layers,
        }

    def _check_fs_latency(self, root_path: str) -> float:
        """Measure filesystem latency for a typical read operation."""
        start = time.time()
        p = Path(root_path)
        list(p.iterdir())
        return (time.time() - start) * 1000

    def diagnose(self) -> Dict[str, Any]:
        """Full diagnostic report of the architecture."""
        metrics = self.get_health_metrics(".")

        issues = []

        if metrics["fs_latency_ms"] > 100:
            issues.append("High filesystem latency detected")

        if metrics["total_symbols"] == 0:
            issues.append("No symbols indexed")

        # Check layer distribution
        layers = metrics.get("layers", {})
        if "layer_1" not in layers:
            issues.append("No Layer 1 (code->code) edges found")

        return {"healthy": len(issues) == 0, "issues": issues, "metrics": metrics}
