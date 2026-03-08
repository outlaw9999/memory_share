from pathlib import Path
from typing import Any, Optional, Set

from .graph_store import GraphStore
from .scanner import Scanner


class AtlasIndexer:
    """Incremental bridge from WAL-driven events to the graph store."""

    def __init__(self, workspace_root: str = ".", scanner: Optional[Scanner] = None, graph_store: Optional[GraphStore] = None):
        self.workspace_root = Path(workspace_root)
        self.scanner = scanner or Scanner()
        self.graph = graph_store or GraphStore(self.workspace_root / ".antigravity" / "atlas" / "atlas.db")
        self.dirty_files: Set[str] = set()
        self._dirty_txns: dict[str, tuple[Optional[str], Optional[float]]] = {}

    def mark_dirty(self, path: str, txn_id: Optional[str] = None, ts: Optional[float] = None) -> None:
        self.dirty_files.add(path)
        if txn_id is not None:
            self._dirty_txns[path] = (txn_id, ts)

    def handle_event(self, event: Any) -> None:
        path = self._extract_path(event)
        if path:
            self.mark_dirty(path, txn_id=self._extract_txn_id(event), ts=self._extract_ts(event))

    def poll(self, max_files: Optional[int] = None) -> list[str]:
        processed: list[str] = []
        while self.dirty_files and (max_files is None or len(processed) < max_files):
            path = self.dirty_files.pop()
            if self._index_file(path):
                processed.append(path)
            self._dirty_txns.pop(path, None)
        return processed

    def _index_file(self, path: str) -> bool:
        resolved = self._resolve_path(path)
        symbols = self.scanner.scan_file(resolved)
        txn_id, ts = self._dirty_txns.get(path, (None, None))
        return self.graph.update_file(resolved, symbols, txn_id=txn_id, ts=ts)

    def _resolve_path(self, path: str) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.workspace_root / candidate

    def _extract_txn_id(self, event: Any) -> Optional[str]:
        txn = getattr(event, "txn", None)
        if isinstance(txn, dict):
            txn_id = txn.get("txn_id")
            if isinstance(txn_id, str):
                return txn_id
        if isinstance(event, dict):
            txn_id = event.get("txn_id")
            if isinstance(txn_id, str):
                return txn_id
        return None

    def _extract_ts(self, event: Any) -> Optional[float]:
        txn = getattr(event, "txn", None)
        if isinstance(txn, dict):
            ts = txn.get("ts")
            if isinstance(ts, int | float):
                return float(ts)
        if isinstance(event, dict):
            ts = event.get("ts")
            if isinstance(ts, int | float):
                return float(ts)
        return None

    def _extract_path(self, event: Any) -> Optional[str]:
        txn = getattr(event, "txn", None)
        if isinstance(txn, dict):
            target = txn.get("target")
            if isinstance(target, str):
                return target
            node = txn.get("node")
            if isinstance(node, dict):
                path = node.get("path")
                if isinstance(path, str):
                    return path

        node = getattr(event, "node", None)
        if isinstance(node, dict):
            path = node.get("path")
            if isinstance(path, str):
                return path

        if isinstance(event, dict):
            target = event.get("target")
            if isinstance(target, str):
                return target

        return None
