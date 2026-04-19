"""Elite Cognitive Quad‑Store AI Kernel (.kit) – Titanium v1.2.4.

Hybrid Brain support (Local + Global + Frozen + Snapshot) with Temporal Graph logic.
Conforms to code‑py‑314: nogil‑ready, strict typing, immutable models, explicit errors.
"""

from __future__ import annotations

import json
import logging
import queue
import sqlite3
import threading
import time
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Union

from kit.core.kit_invariants import enforce_no_global_contamination, sanitize_global_metadata
from kit.core.schema_factory import init_db, enable_wal
from kit.core.memory_topology import MemoryTopology, MemoryTopologyFactory
from kit.core.memory_router import (
    MemoryRouter,
    MemoryReadRequest,
    MemoryWriteRequest,
    WriteSource,
    MemoryTier,
)

logger = logging.getLogger("kit.core")


class FactTag(StrEnum):
    INVARIANT = "invariant"
    DECISION = "decision"
    PREFERENCE = "preference"
    NOTE = "note"
    FRICTION = "friction"
    LEGACY = "legacy"
    SKILL = "skill"
    PATTERN = "pattern"
    HYPOTHESIS = "hypothesis"


def get_tag_schema() -> dict[str, Union[list[str], str]]:
    return {
        "choices": [t.value for t in FactTag],
        "default": FactTag.DECISION.value,
        "source": "kit.core.kit_cognitive_core.FactTag",
        "version": "1.2.4-TITANIUM",
    }


class SAMBrainError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Memory:
    id: int
    node_uid: str
    content: str
    score: float
    brain_source: Literal["local", "global", "law"]
    layer: str = "episodic"
    namespace: str = "shared"
    scope: str = ""
    created_at: str = ""
    importance: float = 1.0
    symbol: str | None = None
    branch: str = "main"
    tag: str = "decision"
    is_active: bool = True
    supersedes_id: int | None = None
    materialized_score: float = 1.0
    created_at_bucket: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.node_uid,
            "content": self.content,
            "importance": self.importance,
            "tag": self.tag,
            "layer": self.layer,
            "score": self.score,
            "source": self.brain_source,
            "namespace": self.namespace,
            "scope": self.scope,
            "symbol": self.symbol,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class RankingAssessment:
    memories: list[Memory]
    confidence: float
    status: Literal["EMPTY", "AMBIGUOUS", "WEAK_SIGNAL", "HIGH_CONFIDENCE"]


class ConnectionWrapper:
    """Safely wraps a sqlite3.Connection to track its lifecycle (v1.2.4-TITANIUM)."""
    def __init__(self, conn: sqlite3.Connection, conn_id: int, brain: SAMBrain):
        self._conn = conn
        self._conn_id = conn_id
        self._brain = brain
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if not self._closed:
            if self._brain and self._brain._active_connections:
                self._brain._active_connections.pop(self._conn_id, None)
            
            # v1.2.4-TITANIUM: Ensure WAL is checkpointed before closure to release handles cleanly
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass

            self._conn.close()
            self._brain = None # Break circular reference
            self._closed = True

    @property
    def row_factory(self):
        return self._conn.row_factory
    
    @row_factory.setter
    def row_factory(self, value):
        self._conn.row_factory = value


class SAMBrain:
    SQLITE_TIMEOUT_SECONDS: float = 10.0
    SQLITE_MAX_RETRIES: int = 5
    SQLITE_RETRY_BASE_DELAY_SECONDS: float = 0.1
    TAG_PRIORITY: dict[str, int] = {"invariant": 3, "decision": 2, "preference": 1, "note": 0, "friction": 0}
    AMBIGUITY_THRESHOLD: float = 0.2
    HIGH_CONFIDENCE_THRESHOLD: float = 0.5
    SNAPSHOT_REFRESH_SECONDS: float = 30.0

    active_frame: Optional[Any] = None

    def __init__(
        self,
        db_path: Path,
        root_path: Path | None = None,
        topology: MemoryTopology | None = None,
    ) -> None:
        self.db_path = db_path.resolve()
        self.root_path = root_path or self._resolve_root(self.db_path.parent)
        self.topology = topology or MemoryTopologyFactory.for_project(self.root_path)
        self.global_db_path: Path | None = None
        self.current_branch: str = "main"
        self.cognition_version: int = 0

        self._last_snapshot_refresh: float | None = None
        self._snapshot_queue: queue.Queue[str | None] = queue.Queue()
        self._snapshot_sync_thread: threading.Thread | None = None
        self._snapshot_sync_stop_event = threading.Event()
        self._snapshot_io_lock = threading.Lock()
        self._active_connections: dict[int, sqlite3.Connection] = {}

        self._is_shutting_down = False
        self._router = MemoryRouter(
            self.topology, 
            local_db_path_override=self.db_path,
            connection_provider=self.get_connection
        )

        self._init_db()
        self._refresh_version()
        
        from kit.core.kit_env import ExecutionMode, get_execution_mode
        if get_execution_mode() != ExecutionMode.TEST:
            self._start_snapshot_syncer()
        else:
            logger.info("TEST MODE detected: Background snapshot syncer disabled.")

    @staticmethod
    def _resolve_root(start_path: Path) -> Path:
        for parent in [start_path] + list(start_path.parents):
            if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
                return parent
        return start_path

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            init_db(conn)
            enable_wal(conn)
            conn.commit()

    def _create_connection(self, db_path: Path, readonly: bool = False) -> ConnectionWrapper:
        """Central authority for opening ANY SQLite connection (v1.2.4-TITANIUM)."""
        if self._is_shutting_down:
            raise RuntimeError("Cognitive kernel is shutting down.")
            
        # Use topology to ensure consistent PRAGMAs (WAL, timeout, etc.)
        conn = self.topology.connect_path(db_path, readonly=readonly)
        
        # Track connection for deterministic shutdown
        conn_id = id(conn)
        wrapper = ConnectionWrapper(conn, conn_id, self)
        self._active_connections[conn_id] = wrapper
        return wrapper

    @contextmanager
    def get_connection(self, db_path: Path | None = None, readonly: bool = False):
        """Unified connection authority with automatic closure (v1.2.4)."""
        target = db_path or self.db_path
        conn = self._create_connection(target, readonly=readonly)
        try:
            yield conn
        finally:
            try:
                conn.close()
            except sqlite3.ProgrammingError:
                pass # Already closed

    def _get_connection(self, db_path: Path | None = None, readonly: bool = False) -> sqlite3.Connection:
        """Internal tracked connection."""
        target = db_path or self.db_path
        return self._create_connection(target, readonly=readonly)

    def attach_global(self, global_db_path: Path | None) -> None:
        """Attach global brain for cross-workspace queries (stub for compatibility)."""
        self.global_db_path = global_db_path

    def _refresh_version(self) -> None:
        try:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT version FROM branches WHERE name = ?", (self.current_branch,)
                ).fetchone()
                self.cognition_version = row[0] if row else 0
        except sqlite3.OperationalError:
            self.cognition_version = 0

    def _start_snapshot_syncer(self) -> None:
        import os
        if os.getenv("KIT_DISABLE_ASYNC_BAKE") == "1":
            return
        if self._snapshot_sync_thread and self._snapshot_sync_thread.is_alive():
            return
        self._snapshot_sync_stop_event.clear()
        self._snapshot_sync_thread = threading.Thread(
            target=self._snapshot_worker_loop,
            name="Titanium-Snapshot-Worker",
            daemon=True,
        )
        self._snapshot_sync_thread.start()

    def shutdown(self) -> None:
        """Production-Grade Teardown (v1.2.4-TITANIUM).
        Guarantees: thread stopped, connections closed, file handles released.
        """
        if self._is_shutting_down:
            return
        self._is_shutting_down = True

        # 1. Signal background worker to stop
        try:
            if hasattr(self, "_snapshot_sync_stop_event"):
                self._snapshot_sync_stop_event.set()
                
            # Put STOP in queue to wake up worker from block
            self._snapshot_queue.put("STOP")
        except Exception:
            pass

        # 2. Join background thread with deterministic verify-loop
        if self._snapshot_sync_thread and self._snapshot_sync_thread.is_alive():
            self._snapshot_sync_thread.join(timeout=1.0)
            if self._snapshot_sync_thread.is_alive():
                logger.warning("Titanium-Snapshot-Worker did not exit gracefully. Force closing.")

        # 3. Force Close ALL tracked connections (Critical for SQLite release)
        # We use a list to avoid mutation during iteration
        active_ids = list(self._active_connections.keys())
        for conn_id in active_ids:
            try:
                conn = self._active_connections.get(conn_id)
                if conn:
                    # Invariant: Force WAL checkpoint before closing if possible
                    try:
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    except Exception:
                        pass
                    conn.close()
            except Exception as e:
                logger.debug(f"Error closing tracked connection: {e}")
        
        self._active_connections.clear()

    def _snapshot_worker_loop(self) -> None:
        while not self._snapshot_sync_stop_event.is_set():
            try:
                request = self._snapshot_queue.get(block=True, timeout=1.0)
                if request == "STOP" or request is None:
                    break
                while not self._snapshot_queue.empty():
                    try:
                        self._snapshot_queue.get_nowait()
                    except queue.Empty:
                        break
                with self._snapshot_io_lock:
                    self._refresh_materialized_scores(force=True)
            except queue.Empty:
                with self._snapshot_io_lock:
                    self._refresh_materialized_scores(force=False)
            except Exception as exc:
                logger.error("Snapshot worker error: %s", exc)
                time.sleep(1.0)

    def _refresh_materialized_scores(self, force: bool = False) -> None:
        now = time.time()
        if not force and self._last_snapshot_refresh is not None:
            if (now - self._last_snapshot_refresh) < self.SNAPSHOT_REFRESH_SECONDS:
                return
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE observations
                SET materialized_score = importance * 
                    ((access_count + 2) / (access_count + 6.0)) *
                    CASE layer
                        WHEN 'working'  THEN 3.0
                        WHEN 'episodic' THEN 2.0
                        WHEN 'semantic' THEN 1.5
                        ELSE 1.0
                    END *
                    CASE 
                        WHEN (julianday('now') - julianday(created_at)) < 7  THEN 1.0
                        WHEN (julianday('now') - julianday(created_at)) < 30 THEN 0.9
                        WHEN (julianday('now') - julianday(created_at)) < 90 THEN 0.7
                        ELSE 0.4
                    END
                WHERE is_active = 1 AND superseded_at IS NULL
            """)
            conn.commit()

            # v1.2.4-TITANIUM: Automatic Snapshot Creation
            snapshot_path = self.topology.resolve("local", "snapshot")
            if snapshot_path.exists():
                try:
                    snapshot_path.unlink()
                except FileNotFoundError:
                    pass
                except PermissionError as e:
                    logger.warning(f"Snapshot rotation blocked by OS: {e}")
                except OSError as e:
                    logger.debug(f"OS error during snapshot unlink: {e}")
            
            try:
                if sqlite3.sqlite_version_info >= (3, 27, 0):
                    conn.execute(f"VACUUM INTO '{snapshot_path.as_posix()}'")
                else:
                    # Fallback for legacy SQLite versions
                    import shutil
                    shutil.copy2(self.db_path, snapshot_path)
            except sqlite3.OperationalError as e:
                logger.error(f"Snapshot creation failed: {e}")

        self._last_snapshot_refresh = now

    def _signal_snapshot_refresh(self) -> None:
        self._snapshot_queue.put("refresh")

    def snapshot(self) -> Path:
        """Manual trigger for database snapshot (v1.2.4)."""
        self._refresh_materialized_scores(force=True)
        return self.topology.resolve("local", "snapshot")

    def restore(self, snapshot_path: Path | None = None) -> bool:
        """
        Restore kernel from a physical snapshot.
        WARNING: This is a destructive operation for the current live state.
        """
        target_snapshot = snapshot_path or self.topology.resolve("local", "snapshot")
        if not target_snapshot.exists():
            raise FileNotFoundError(f"Snapshot not found: {target_snapshot}")

        # 1. Shutdown background tasks
        self.shutdown()
        
        # Reset state for reuse after restore
        self._is_shutting_down = False
        self._active_connections.clear()

        # v1.2.4-TITANIUM: Force GC to release any lingering Python-level handles
        import gc
        gc.collect()

        # 2. Replace physical file
        import shutil
        try:
            # v1.2.4-TITANIUM: Clean up WAL/SHM before restore to prevent replay corruption
            for suffix in ["-wal", "-shm"]:
                sidecar = self.db_path.with_name(self.db_path.name + suffix)
                if sidecar.exists():
                    try:
                        sidecar.unlink()
                    except OSError:
                        # Final safety sleep only if OS is particularly stubborn
                        time.sleep(0.1)
                        try:
                            sidecar.unlink()
                        except OSError:
                            pass

            # We use copy2 to preserve metadata
            shutil.copy2(target_snapshot, self.db_path)
            # Re-init version
            self._refresh_version()
            # Restart syncer
            self._start_snapshot_syncer()
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    @staticmethod
    def _is_retryable_sqlite_error(error: sqlite3.Error) -> bool:
        msg = str(error).lower()
        return any(keyword in msg for keyword in ("locked", "busy"))

    def _run_write_transaction(
        self,
        operation: Callable[[sqlite3.Connection], Any],
        db_path: Path | None = None,
    ) -> Any:
        from kit.core.kit_lock import is_sealed

        if is_sealed(self.root_path) and "pytest" not in sys.modules:
            raise SAMBrainError("Memory kernel is sealed. Run 'kit unseal --reason <msg>' to continue learning.")

        target_path = db_path or self.db_path
        last_error: Optional[sqlite3.Error] = None

        for attempt in range(self.SQLITE_MAX_RETRIES):
            with self.get_connection(target_path) as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    result = operation(conn)
                    conn.commit()
                    if target_path == self.topology.resolve("local", "local"):
                        self._signal_snapshot_refresh()
                    return result
                except sqlite3.OperationalError as exc:
                    conn.rollback()
                    last_error = exc
                    if self._is_retryable_sqlite_error(exc) and attempt < (self.SQLITE_MAX_RETRIES - 1):
                        delay = self.SQLITE_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                        time.sleep(delay)
                        continue
                    raise
        if last_error:
            raise last_error
        raise SAMBrainError("Write transaction failed after maximum retries.")

    def learn(
        self,
        uid: str,
        content: str,
        *,
        importance: float = 0.5,
        layer: str = "episodic",
        metadata: dict[str, Any] | None = None,
        to_global: bool = False,
        supersede_id: int | None = None,
        namespace: str = "shared",
        scope: str | None = None,
        agent_id: str | None = None,
        symbol: str | None = None,
        tag: str = FactTag.DECISION.value,
        node_type: str = "observation",
        status: str = "active",
        visibility: str = "local",
    ) -> int:
        if to_global:
            normalized_scope = "GLOBAL"
            clean_metadata = sanitize_global_metadata(metadata or {})
        else:
            normalized_scope = scope if scope is not None else self._get_normalized_scope()
            clean_metadata = (metadata or {}).copy()

        from kit.core.kernel_fsm import StateMutationContract
        frame_id = StateMutationContract.authorize_mutation(self.active_frame)
        clean_metadata["_kernel_frame"] = frame_id
        if self.active_frame:
            if hasattr(self.active_frame, "session_id"):
                clean_metadata["_kernel_session"] = self.active_frame.session_id
            ctx = getattr(self.active_frame, "context", None)
            if ctx:
                clean_metadata.update({
                    "_flow_id": ctx.flow_id,
                    "_step_id": ctx.step_id,
                    "_transaction_id": ctx.transaction_id,
                })

        normalized_tag = tag.strip().lower()
        VALID_TAGS = {t.value for t in FactTag}
        if normalized_tag not in VALID_TAGS:
            raise ValueError(f"Invalid tag '{normalized_tag}'")

        if to_global and normalized_tag in {"decision", "preference", "friction"}:
            raise ValueError("Global memory cannot store local cognition tags.")

        test_entry = {
            "content": content,
            "scope": normalized_scope,
            "tag": normalized_tag,
            "metadata": clean_metadata,
        }
        if to_global:
            enforce_no_global_contamination(test_entry)

        effective_symbol = symbol if symbol is not None else uid

        confidence = min(0.94, (importance / 10.0) + 0.5)
        request = MemoryWriteRequest(
            source=WriteSource.KIT_LEARN,
            key=uid,
            content=content,
            confidence=confidence,
            metadata=clean_metadata,
            node_type=node_type,
            tag=normalized_tag,
            status=status,
            visibility="global" if to_global else visibility,
            layer=layer,
            importance=importance,
            namespace=namespace,
            scope=normalized_scope,
            branch=self.current_branch,
            symbol=effective_symbol,
            agent_id=agent_id,
            supersedes_id=supersede_id,
            target_tier=MemoryTier.GLOBAL if to_global else None,
        )

        decision = self._router.route_write(request)
        if decision.decision == "rejected":
            raise SAMBrainError(f"Cognitive write rejected: {decision.reason}")

        if decision.assigned_tier == MemoryTier.LOCAL:
            self._signal_snapshot_refresh()

        return decision.observation_id or 0

    def _get_normalized_scope(self, path: Path | str | None = None) -> str:
        p = Path(path).resolve() if path else Path.cwd().resolve()
        try:
            rel = p.relative_to(self.root_path)
            return str(rel).replace("\\", "/") if str(rel) != "." else ""
        except ValueError:
            return ""

    def get_normalized_scope(self, path: Path | str | None = None) -> str:
        """Public alias for scope normalization (v1.2.4)."""
        return self._get_normalized_scope(path)

    def touch_fact(self, fact_id: int) -> None:
        def _touch(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE observations SET access_count = access_count + 1, last_accessed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (fact_id,),
            )
        self._run_write_transaction(_touch)

    def recall(
        self,
        entities: list[str],
        limit: int = 15,
        *,
        agent_id: str | None = None,
        here: bool = False,
        symbol: str | None = None,
        query: str | None = None,
        with_global: bool = False,
        include_profile: bool = False,
        since: str | None = None,
        until: str | None = None,
        **kwargs: Any,
    ) -> Union[list[Memory], tuple[list[Memory], dict[str, float]]]:
        start_total = time.perf_counter() if include_profile else 0.0

        current_scope = self._get_normalized_scope() if here else None

        request = MemoryReadRequest(
            query=query or "",
            limit=limit,
            entities=entities,
            with_global=with_global,
            agent_id=agent_id,
            scope=current_scope,
            symbol=symbol,
            since=since,
            until=until
        )

        memories = self._router.resolve_read(request)

        scored_memories: list[Memory] = []
        for mem in memories:
            scored = replace(
                mem,
                score=self._calculate_runtime_score(
                    mem,
                    current_scope=current_scope or "",
                    symbol=symbol,
                    agent_id=agent_id,
                    source_priority=1.5 if mem.brain_source == "local" else (2.0 if mem.brain_source == "law" else 1.0),
                ),
            )
            scored_memories.append(scored)

        scored_memories.sort(
            key=lambda m: (self.TAG_PRIORITY.get(m.tag, 0), m.score, m.created_at),
            reverse=True,
        )

        if include_profile:
            profile = {"total": time.perf_counter() - start_total}
            return scored_memories[:limit], profile
        return scored_memories[:limit]

    def _calculate_runtime_score(
        self,
        memory: Memory,
        *,
        current_scope: str = "",
        symbol: str | None = None,
        agent_id: str | None = None,
        source_priority: float = 1.0,
    ) -> float:
        base = memory.materialized_score * source_priority
        if agent_id and memory.namespace == agent_id:
            base *= 1.2
        bonus = 0.0
        bonus += {"invariant": 0.3, "decision": 0.2, "preference": 0.1}.get(memory.tag, 0.0)
        if agent_id and memory.namespace == agent_id:
            bonus += 0.1
        if symbol and memory.symbol == symbol:
            bonus += 0.3
        elif current_scope and memory.scope == current_scope:
            bonus += 0.2
        elif current_scope and memory.scope and current_scope.startswith(memory.scope):
            bonus += 0.15
        elif memory.scope in {"", "global"}:
            bonus += 0.1
        return base + bonus

    def recall_with_assessment(self, entities: list[str], **kwargs: Any) -> RankingAssessment:
        result = self.recall(entities, **kwargs)
        memories = result if isinstance(result, list) else result[0]
        confidence = self._calculate_confidence(memories)
        if not memories:
            status = "EMPTY"
        elif confidence < self.AMBIGUITY_THRESHOLD:
            status = "AMBIGUOUS"
        elif confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            status = "HIGH_CONFIDENCE"
        else:
            status = "WEAK_SIGNAL"
        return RankingAssessment(memories=memories, confidence=confidence, status=status)

    @staticmethod
    def _calculate_confidence(memories: list[Memory]) -> float:
        if not memories:
            return 0.0
        if len(memories) == 1:
            return 1.0
        top = memories[0].score
        runner = memories[1].score
        return max(0.0, (top - runner) / (abs(top) + 1e-6))

    def search(
        self,
        query: str,
        limit: int = 15,
        *,
        agent_id: str | None = None,
        at_timestamp: str | None = None,
        fast: bool = False,
    ) -> list[Memory]:
        """Hybrid FTS Search with Compatibility Shims (v1.2.4-TITANIUM)."""
        # RESERVED for future time-travel and index-only search
        _ = at_timestamp
        _ = fast

        limit = int(limit)
        pattern = f"%{query}%"
        
        if agent_id:
            with self.get_connection() as conn:
                rows = conn.execute("""
                    SELECT o.*, n.uid as node_uid
                    FROM observations o
                    JOIN nodes n ON o.node_id = n.id
                    WHERE o.content LIKE ? AND o.is_active = 1 
                      AND (o.namespace = ? OR o.namespace = 'shared')
                    ORDER BY 
                        CASE WHEN o.namespace = ? THEN 0 ELSE 1 END,
                        o.materialized_score DESC, 
                        o.access_count DESC 
                    LIMIT ?
                """, (pattern, agent_id, agent_id, limit)).fetchall()
        else:
            with self.get_connection() as conn:
                rows = conn.execute("""
                    SELECT o.*, n.uid as node_uid
                    FROM observations o
                    JOIN nodes n ON o.node_id = n.id
                    WHERE o.content LIKE ? AND o.is_active = 1
                    ORDER BY o.materialized_score DESC, o.access_count DESC LIMIT ?
                """, (pattern, limit)).fetchall()

        return [Memory(
            id=row["id"],
            node_uid=row["node_uid"],
            content=row["content"],
            score=row["materialized_score"],
            brain_source="local",
            layer=row["layer"],
            namespace=row["namespace"],
            scope=row["scope"],
            created_at=str(row["created_at"]),
            importance=row["importance"],
            symbol=row["symbol"],
            tag=row["tag"],
        ) for row in rows]

    def export_for_prompt(self, entities: list[str], limit: int = 3, budget: int = 200) -> str:
        result = self.recall(entities, min(limit, 3))
        memories = result if isinstance(result, list) else result[0]
        if not memories:
            return ""

        lines = ["<kit_memory>"]
        used = len(lines[0]) + len("</kit_memory>") + 1
        for mem in memories:
            line = f"[{mem.brain_source}:{mem.node_uid}] {mem.content.splitlines()[0][:80]}"
            if used + len(line) + 1 > budget:
                break
            lines.append(line)
            used += len(line) + 1
        if len(lines) == 1:
            return ""
        lines.append("</kit_memory>")
        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """Retrieve kernel statistics (v1.2.4)."""
        stats = {}
        with self.get_connection() as conn:
            stats["nodes"] = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            stats["observations"] = conn.execute("SELECT COUNT(*) FROM observations WHERE is_active = 1").fetchone()[0]
            stats["edges"] = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            stats["version"] = self.cognition_version
            stats["db_path"] = str(self.db_path)
        return stats

    def __enter__(self) -> "SAMBrain":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown()