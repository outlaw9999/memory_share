import hashlib
import time
from pathlib import Path
from typing import Any, Optional, Set

from .graph_store import GraphStore
from .scanner import Scanner
from .incremental_updater import IncrementalUpdater, SymbolHasher


class AtlasIndexer:
    """Incremental bridge from WAL-driven events to the graph store."""

    def __init__(self, workspace_root: str = ".", scanner: Optional[Scanner] = None, graph_store: Optional[GraphStore] = None):
        self.workspace_root = Path(workspace_root)
        self.scanner = scanner or Scanner()
        self.graph = graph_store or GraphStore(self.workspace_root / ".antigravity" / "atlas" / "atlas.db")
        self.incremental_updater = IncrementalUpdater(self.graph.db_path)
        self.dirty_files: Set[str] = set()
        self._dirty_txns: dict[str, tuple[Optional[str], Optional[float]]] = {}
        self._dirty_seen_at: dict[str, float] = {}
        self._file_hashes: dict[str, str] = {}  # Track file content hashes for change detection
        self.coalesce_window_seconds = 0.2
        self.use_incremental = True  # Enable incremental indexing by default
        self.txn_retention_seconds = 7 * 24 * 60 * 60
        self.cleanup_interval_seconds = 60 * 60
        self._last_cleanup_at = 0.0

    def mark_dirty(self, path: str, txn_id: Optional[str] = None, ts: Optional[float] = None) -> None:
        self.dirty_files.add(path)
        self._dirty_seen_at[path] = time.time()
        if txn_id is not None:
            self._dirty_txns[path] = (txn_id, ts)

    def handle_event(self, event: Any) -> None:
        path = self._extract_path(event)
        if path:
            self.mark_dirty(path, txn_id=self._extract_txn_id(event), ts=self._extract_ts(event))

    def poll(self, max_files: Optional[int] = None) -> list[str]:
        processed: list[str] = []
        self._maybe_cleanup()
        self._prune_missing_dirty_paths()
        now = time.time()
        while self.dirty_files and (max_files is None or len(processed) < max_files):
            path = self._pop_ready_path(now)
            if path is None:
                break
            status = self._index_file(path)
            if status == "applied":
                processed.append(path)
                self._dirty_txns.pop(path, None)
                self._dirty_seen_at.pop(path, None)
            elif status == "duplicate":
                self._dirty_txns.pop(path, None)
                self._dirty_seen_at.pop(path, None)
            elif status == "retry":
                break
        return processed

    def _index_file(self, path: str) -> str:
        """
        Index a single file using incremental update strategy.
        
        Returns:
            "applied" - index was updated
            "duplicate" - no actual changes
            "retry" - file is changing, try again later
        """
        resolved = self._resolve_path(path)
        
        # Step 1: Content stability check (file not changing during scan)
        before = self._snapshot_token(resolved)
        symbols = self.scanner.scan_file(resolved)
        scan_calls = getattr(self.scanner, "scan_calls", None)
        calls = scan_calls(resolved) if callable(scan_calls) else []
        after = self._snapshot_token(resolved)
        
        if before != after:
            # File changed during scan - retry later
            txn_id, ts = self._dirty_txns.get(path, (None, None))
            self.mark_dirty(path, txn_id=txn_id, ts=ts)
            return "retry"
        
        txn_id, ts = self._dirty_txns.get(path, (None, None))
        
        # Step 2: Use incremental updater if enabled
        if self.use_incremental:
            success = self.incremental_updater.update_file_delta(
                str(resolved),
                new_symbols=self._normalize_symbols(symbols),
                new_edges=self._normalize_edges(calls),
                txn_id=txn_id,
                ts=ts
            )
            
            if success:
                return "applied"
            else:
                return "duplicate"
        else:
            # Fallback to old-style update
            if self.graph.update_file(resolved, symbols, calls, txn_id=txn_id, ts=ts):
                return "applied"
            return "duplicate"

    def _normalize_symbols(self, symbols: list) -> list[dict]:
        """
        Convert scanner output to format expected by incremental updater.
        
        Expected format: {name, kind, line, [signature, body]}
        """
        normalized = []
        for sym in symbols:
            # Handle different symbol format
            if isinstance(sym, dict):
                normalized.append({
                    "name": sym.get("name", ""),
                    "kind": sym.get("kind", ""),
                    "line": sym.get("line", 0),
                    "signature": sym.get("signature", ""),
                    "body": sym.get("body", "")
                })
        return normalized

    def _normalize_edges(self, calls: list) -> list[dict]:
        """
        Convert scanner call output to format expected by incremental updater.
        
        Expected format: {caller, callee, file, line}
        """
        normalized = []
        for call in calls:
            if isinstance(call, dict):
                normalized.append({
                    "caller": call.get("caller", ""),
                    "callee": call.get("callee", ""),
                    "file": call.get("file", ""),
                    "line": call.get("line", 0)
                })
        return normalized

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

    def _snapshot_token(self, path: Path) -> tuple[bool, str]:
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            return (False, "")
        return (True, hashlib.sha1(content).hexdigest())

    def _maybe_cleanup(self) -> None:
        if self.txn_retention_seconds <= 0:
            return
        now = time.time()
        if now - self._last_cleanup_at < self.cleanup_interval_seconds:
            return
        self.graph.cleanup_applied_txns(self.txn_retention_seconds, now=now)
        self._last_cleanup_at = now

    def _prune_missing_dirty_paths(self) -> None:
        missing_paths = [path for path in self.dirty_files if not self._resolve_path(path).exists()]
        for path in missing_paths:
            self.dirty_files.discard(path)
            self._dirty_seen_at.pop(path, None)
            self._dirty_txns.pop(path, None)

    def _pop_ready_path(self, now: float) -> Optional[str]:
        ready_path: Optional[str] = None
        oldest_seen = now
        for path in self.dirty_files:
            seen_at = self._dirty_seen_at.get(path, 0.0)
            if now - seen_at < self.coalesce_window_seconds:
                continue
            if ready_path is None or seen_at < oldest_seen:
                ready_path = path
                oldest_seen = seen_at

        if ready_path is not None:
            self.dirty_files.remove(ready_path)
        return ready_path
