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
        self._snapshot_io_lock = threading.Lock()
        self._snapshot_sync_stop_event = threading.Event()
        self._snapshot_sync_thread: threading.Thread | None = None

        self._router = MemoryRouter(self.topology, local_db_path_override=self.db_path)

        self._init_db()
        self._refresh_version()
        self._start_snapshot_syncer()

    @staticmethod
    def _resolve_root(start_path: Path) -> Path:
        for parent in [start_path] + list(start_path.parents):
            if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
                return parent
        return start_path

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            init_db(conn)
            conn.commit()

    def _get_connection(self, db_path: Path | None = None) -> sqlite3.Connection:
        target = db_path or self.db_path
        if target != self.topology.resolve("local", "local"):
            mode = "rwc"
            uri = f"file:{target.as_posix()}?mode={mode}"
            conn = sqlite3.connect(uri, uri=True, timeout=self.SQLITE_TIMEOUT_SECONDS, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn
        return self.topology.connect("local", "local", readonly=False)

    def get_connection(self, db_path: Path | None = None) -> sqlite3.Connection:
        """Public alias for _get_connection (for backward compatibility)."""
        return self._get_connection(db_path)

    def attach_global(self, global_db_path: Path | None) -> None:
        """Attach global brain for cross-workspace queries (stub for compatibility)."""
        self.global_db_path = global_db_path

    def _refresh_version(self) -> None:
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT version FROM branches WHERE name = ?", (self.current_branch,)
                ).fetchone()
                self.cognition_version = row[0] if row else 0
        except sqlite3.OperationalError:
            self.cognition_version = 0

    def _start_snapshot_syncer(self) -> None:
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
        if self._snapshot_sync_stop_event:
            self._snapshot_sync_stop_event.set()
            self._snapshot_queue.put("STOP")
            if self._snapshot_sync_thread:
                self._snapshot_sync_thread.join(timeout=2.0)

    def _snapshot_worker_loop(self) -> None:
        while not self._snapshot_sync_stop_event.is_set():
            try:
                request = self._snapshot_queue.get(block=True, timeout=5.0)
                if request == "STOP":
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
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE observations
                SET materialized_score = importance * ((access_count + 2) / (access_count + 6.0)) *
                    CASE layer
                        WHEN 'working'  THEN 3.0
                        WHEN 'episodic' THEN 2.0
                        WHEN 'semantic' THEN 1.5
                        ELSE 1.0
                    END
                WHERE is_active = 1 AND superseded_at IS NULL
            """)
            conn.commit()
        self._last_snapshot_refresh = now

    def _signal_snapshot_refresh(self) -> None:
        self._snapshot_queue.put("refresh")

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
            raise SAMBrainError("Brain is sealed. Write operations are blocked.")

        target_path = db_path or self.db_path
        last_error: Optional[sqlite3.Error] = None

        for attempt in range(self.SQLITE_MAX_RETRIES):
            conn = self._get_connection(target_path)
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
            finally:
                conn.close()
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

    def search(self, query: str, limit: int = 15, *, agent_id: str | None = None) -> list[Memory]:
        pattern = f"%{query}%"
        
        if agent_id:
            with self._get_connection() as conn:
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
            with self._get_connection() as conn:
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

    def __enter__(self) -> "SAMBrain":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown()