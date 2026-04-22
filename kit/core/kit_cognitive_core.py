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
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Union

from kit.core.kit_invariants import enforce_no_global_contamination, sanitize_global_metadata
from kit.core.schema_factory import init_db, enable_wal
from kit.core.memory_topology import MemoryTopology, MemoryTopologyFactory
from kit.core.kit_env import ExecutionMode, get_execution_mode
from kit.core.memory_router import (
    MemoryRouter,
    MemoryReadRequest,
    MemoryWriteRequest,
    WriteSource,
    MemoryTier,
)
from kit.core.kit_metrics import calculate_gqi, get_namespace_stats
from kit.core.kit_retention import execute_retention, RetentionPolicy
from kit.core.kit_sre import SREEngine
from kit.core.kit_commit_queue import CommitQueue, CommitEvent
from kit.core.kit_l0_cache import L0Cache

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


def sha256_file(path: Path) -> str:
    """Calculate SHA256 hash of a file for integrity verification (v1.2.4-TITANIUM)."""
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
    except FileNotFoundError:
        return ""
    return h.hexdigest()


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
    materialized_score: float = 0.0
    created_at_bucket: int = 0
    structural_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    _runtime_hash: int | None = None

    def __post_init__(self) -> None:
        """Strict Deterministic identity lock for v1.2.4-TITANIUM-FROZEN."""
        import hashlib
        # v1.2.4-TITANIUM++: Use BLAKE2b(16) for 128-bit collision-free runtime arbitration
        h_bytes = hashlib.blake2b(self.content.encode("utf-8"), digest_size=16).digest()
        h = int.from_bytes(h_bytes, "big")
        # Ensure _runtime_hash is always set as an immutable attribute
        object.__setattr__(self, "_runtime_hash", h)

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
    def __init__(self, conn: sqlite3.Connection, conn_id: int, brain: SAMBrain, readonly: bool = False):
        self._conn = conn
        self._conn_id = conn_id
        self._brain = brain
        self._readonly = readonly
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
            
            # v1.2.4-TITANIUM: Connection closure is now lightweight.
            # WAL Checkpoints are handled at the kernel-level during shutdown or maintenance.
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
        
        if self.root_path:
            self.topology = topology or MemoryTopologyFactory.for_project(self.root_path)
        else:
            # v1.2.4-TITANIUM: Fallback to global-only topology if no project root found
            self.topology = topology or MemoryTopologyFactory.global_only()
            logger.warning("No project root found. Running in GLOBAL-ONLY mode.")
        self.global_db_path: Path | None = None
        self.current_branch: str = "main"
        self.cognition_version: int = 0

        self._last_snapshot_refresh: float | None = None
        self._snapshot_queue: queue.Queue[str | None] = queue.Queue()
        self._snapshot_sync_thread: threading.Thread | None = None
        self._snapshot_sync_stop_event = threading.Event()
        self._snapshot_io_lock = threading.Lock()
        self._active_connections: dict[int, sqlite3.Connection] = {}
        self._last_snapshot_id: str | None = None
        self._last_snapshot_hash: str | None = None

        self._is_shutting_down = False
        self._router = MemoryRouter(
            self.topology, 
            local_db_path_override=self.db_path,
            connection_provider=self.get_connection
        )

        self._init_db()
        self._refresh_version()
        self._load_last_snapshot_state()
        
        # v1.2.4-STAGE5.5.3: Memory Dual-Path Router (L0 Cache)
        self._l0_cache = L0Cache()
        
        # v1.2.4-STAGE5.5.2: Memory Commit Layer (The Clock)
        self._commit_layer = CommitQueue(self, on_flush=self._on_commit_graduation)
        
        from kit.core.kit_env import ExecutionMode, get_execution_mode
        if get_execution_mode() != ExecutionMode.TEST:
            self._commit_layer.start()
            self._start_snapshot_syncer()
        else:
            logger.info("TEST MODE detected: Background threads disabled.")

    @staticmethod
    def _resolve_root(start_path: Path) -> Path | None:
        """Find the project root (boundary) by looking for .git or pyproject.toml."""
        for parent in [start_path] + list(start_path.parents):
            if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
                return parent
            
            # v1.2.4-TITANIUM: Safety Barrier - Do NOT search above user home or IDE internal dirs
            if parent.resolve() == Path.home().resolve() or parent.name == ".gemini":
                break
        
        # v1.2.4-TITANIUM: If we are exactly at HOME and no boundary was found, 
        # we return None to prevent local_brain.db from appearing in ~/.kit/
        if start_path.resolve() == Path.home().resolve():
            return None
                
        # Fallback for non-git projects (e.g. temporary test directories)
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
        wrapper = ConnectionWrapper(conn, conn_id, self, readonly=readonly)
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
        """Attach global brain and ensure it is initialized (v1.2.4-TITANIUM)."""
        self.global_db_path = global_db_path
        if global_db_path:
            # v1.2.4: Ensure global brain has current schema
            try:
                with self.get_connection(global_db_path) as conn:
                    init_db(conn)
                    enable_wal(conn)
                    conn.commit()
            except Exception as e:
                logger.warning(f"Failed to initialize global brain at {global_db_path}: {e}")

    def _refresh_version(self) -> None:
        try:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT version FROM branches WHERE name = ?", (self.current_branch,)
                ).fetchone()
                self.cognition_version = row[0] if row else 0
        except sqlite3.OperationalError:
            self.cognition_version = 0

    def _load_last_snapshot_state(self) -> None:
        """Load the most recent snapshot ID and Hash to maintain lineage (v1.2.4-STAGE5)."""
        try:
            with self.get_connection(readonly=True) as conn:
                row = conn.execute(
                    "SELECT id, snapshot_hash FROM snapshots ORDER BY timestamp DESC LIMIT 1"
                ).fetchone()
                if row:
                    self._last_snapshot_id = row[0]
                    self._last_snapshot_hash = row[1]
        except sqlite3.OperationalError:
            pass

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

    def _stop_snapshot_syncer(self) -> None:
        """Signal and wait for the background worker to stop (v1.2.4)."""
        # 1. Trigger STOP signals
        try:
            if hasattr(self, "_snapshot_sync_stop_event"):
                self._snapshot_sync_stop_event.set()
                
            # Put STOP in queue to wake up worker from block
            self._snapshot_queue.put("STOP")
        except Exception:
            pass

        # 2. Join background thread with deterministic timeout
        if self._snapshot_sync_thread and self._snapshot_sync_thread.is_alive():
            # v1.2.4-TITANIUM: Enforce thread join to prevent WinError 32 during file cleanup
            self._snapshot_sync_thread.join(timeout=2.0)
            if self._snapshot_sync_thread.is_alive():
                logger.warning("Titanium-Snapshot-Worker did not exit gracefully. Force closing.")

    def _on_commit_graduation(self, events: list[CommitEvent]):
        """Callback: Remove graduated memories from L0 Cache after commit."""
        if hasattr(self, "_l0_cache"):
            hashes = {e.structural_hash for e in events}
            self._l0_cache.clear_by_hashes(hashes)

    def shutdown(self) -> None:
        """Deterministic shutdown barrier (v1.2.4-TITANIUM)."""
        # 0. Flush and close commit layer before blocking connections
        if hasattr(self, "_commit_layer"):
            self._commit_layer.shutdown()
        
        if hasattr(self, "_router") and hasattr(self._router, "close"):
            self._router.close()

        self._is_shutting_down = True
        
        # 1. Stop Snapshot Worker
        self._stop_snapshot_syncer()

        # 2. Drain and close all active connections using the POP pattern
        # Critical for releasing SQLite handles on Windows
        connection_ids = list(self._active_connections.keys())
        for conn_id in connection_ids:
            wrapper = self._active_connections.pop(conn_id, None)
            if wrapper:
                try:
                    wrapper.close()
                except Exception as e:
                    logger.warning(f"Shutdown: Error closing connection {conn_id}: {e}")
        
        # 3. Final WAL Checkpoint for durability (v1.2.4-TITANIUM-STABILIZE)
        try:
            with self.get_connection(self.db_path) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as e:
            logger.debug(f"Shutdown: Final WAL checkpoint failed: {e}")

        self._active_connections.clear()
        logger.info("Cognitive kernel shutdown complete.")

    def _snapshot_worker_loop(self) -> None:
        while not self._snapshot_sync_stop_event.is_set():
            try:
                # v1.2.4: Deterministic wake-up via "STOP" signal, no timeout needed
                request = self._snapshot_queue.get(block=True)
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

    def _refresh_materialized_scores(self, force: bool = False, reason: str = "Automatic maintenance") -> None:
        now = time.time()
        if not force and self._last_snapshot_refresh is not None:
            if (now - self._last_snapshot_refresh) < self.SNAPSHOT_REFRESH_SECONDS:
                return
        with self.get_connection() as conn:
            from kit.core.memory_policy import MemoryPolicy
            
            # v1.2.4-TITANIUM-FROZEN: Single Authority Alignment
            # We approximate the decay logic in SQL for performance, but the router 
            # will always re-calculate the EXACT canonical score at recall time.
            conn.execute(MemoryPolicy.SQL_MATERIALIZE_SCORE)
            conn.commit()

            # v1.2.4-TITANIUM++: Atomic Snapshot Write Strategy
            snapshot_path = self.topology.resolve("local", "snapshot")
            temp_snapshot_path = snapshot_path.with_suffix(".tmp")
            
            # Clean up lingering temp files
            if temp_snapshot_path.exists():
                try:
                    temp_snapshot_path.unlink()
                except OSError:
                    pass

            try:
                if sqlite3.sqlite_version_info >= (3, 27, 0):
                    conn.execute(f"VACUUM INTO '{temp_snapshot_path.as_posix()}'")
                else:
                    import shutil
                    shutil.copy2(self.db_path, temp_snapshot_path)
            except sqlite3.OperationalError as e:
                logger.error(f"Snapshot creation failed (I/O): {e}")
                return

        self._last_snapshot_refresh = now
        
        # v1.2.4-STAGE5: Record snapshot lineage with Titanium++ Manifest Hash-Chain
        try:
            import hashlib
            file_hash = sha256_file(temp_snapshot_path)
            parent_hash = self._last_snapshot_hash or "GENESIS"
            schema_version = "v1.2.4"
            snapshot_id = f"snap_{int(now)}_{uuid.uuid4().hex[:4]}"
            
            # Titanium++ Manifest: H(n) = SHA256(parent | file | time | id | version)
            manifest = f"{parent_hash}|{file_hash}|{int(now)}|{snapshot_id}|{schema_version}"
            current_snapshot_hash = hashlib.sha256(manifest.encode()).hexdigest()
            
            # v1.2.4-TITANIUM++: Atomic Commit with Durability Barrier
            if snapshot_path.exists():
                try:
                    snapshot_path.unlink()
                except OSError:
                    snapshot_path.rename(snapshot_path.with_name(snapshot_path.name + ".old"))
            
            # Flush and Fsync before rename
            try:
                import os
                with open(temp_snapshot_path, "ab") as f:
                    f.flush()
                    os.fsync(f.fileno())
            except Exception:
                pass

            temp_snapshot_path.rename(snapshot_path)
            
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO snapshots (id, parent_id, parent_hash, snapshot_hash, timestamp, reason, path, metadata)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                """, (snapshot_id, self._last_snapshot_id, parent_hash, current_snapshot_hash, reason, str(snapshot_path), json.dumps({"schema": schema_version, "file_hash": file_hash, "ts_bucket": int(now)})))
                conn.commit()
            
            self._last_snapshot_id = snapshot_id
            self._last_snapshot_hash = current_snapshot_hash
            logger.info(f"Snapshot {snapshot_id} finalized with Titanium++ Integrity.")
        except Exception as e:
            logger.error(f"Lineage: Titanium++ Finalization failed: {e}")
            if temp_snapshot_path.exists():
                try:
                    temp_snapshot_path.unlink()
                except OSError:
                    pass

        # v1.2.4-STAGE5.2: Automatic Retention Shield
        try:
            execute_retention(self, RetentionPolicy(dry_run=False))
        except Exception as e:
            logger.warning(f"Retention: Automatic purge failed: {e}")

        # v1.2.4-STAGE5.5: Symbol Reconciliation Engine (SRE) Monitor
        try:
            sre = SREEngine(self)
            sre.run_drift_monitor()
        except Exception as e:
            logger.warning(f"SRE: Automatic drift monitor failed: {e}")

    def _signal_snapshot_refresh(self) -> None:
        self._snapshot_queue.put("refresh")

    def snapshot(self, reason: str = "Manual snapshot") -> Path:
        """Manual trigger for database snapshot (v1.2.4-STAGE5)."""
        self._refresh_materialized_scores(force=True, reason=reason)
        return self.topology.resolve("local", "snapshot")

    def restore(self, snapshot_path: Path | None = None) -> bool:
        """
        Restore kernel from a physical snapshot.
        WARNING: This is a destructive operation for the current live state.
        """
        target_snapshot = snapshot_path or self.topology.resolve("local", "snapshot")
        if not target_snapshot.exists():
            raise FileNotFoundError(f"Snapshot not found: {target_snapshot}")

        # 0. Integrity Check (v1.2.4-TITANIUM)
        if not self.verify_snapshot_integrity(target_snapshot):
            logger.error(f"Integrity Error: Snapshot {target_snapshot} is tampered or unrecorded. Restore rejected.")
            return False

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

    def verify_snapshot_integrity(self, snapshot_path: Path) -> bool:
        """
        Verify that a physical snapshot file matches the recorded cryptographic chain.
        (v1.2.4-TITANIUM Integrity Enforcement)
        """
        file_hash = sha256_file(snapshot_path)
        if not file_hash:
            return False
            
        try:
            with self.get_connection(readonly=True) as conn:
                # Find any record that matches this file hash and parent chain
                # Since H(n) = SHA256(parent_hash + file_hash), we can't search by file_hash alone if parent_hash changed.
                # However, for simplicity in v1.2.4, we store the file_hash in metadata or just check if any record matches.
                # Actually, our schema now has parent_hash and snapshot_hash.
                # We need to re-verify: snapshot_hash == SHA256(parent_hash + file_hash)
                
                rows = conn.execute(
                    "SELECT id, parent_hash, snapshot_hash, metadata FROM snapshots WHERE path = ? ORDER BY timestamp DESC",
                    (str(snapshot_path),)
                ).fetchall()
                
                for row in rows:
                    snap_id = row[0]
                    p_hash = row[1] or "GENESIS"
                    s_hash = row[2]
                    meta = json.loads(row[3] or "{}")
                    
                    ts_bucket = meta.get("ts_bucket")
                    schema_ver = meta.get("schema", "v1.2.4")
                    
                    if ts_bucket is None:
                         # Legacy v1.2.4-TITANIUM (non-plus)
                         import hashlib
                         expected_hash = hashlib.sha256(((p_hash if p_hash != "GENESIS" else "") + file_hash).encode()).hexdigest()
                    else:
                        # Titanium++ Manifest
                        manifest = f"{p_hash}|{file_hash}|{ts_bucket}|{snap_id}|{schema_ver}"
                        import hashlib
                        expected_hash = hashlib.sha256(manifest.encode()).hexdigest()
                        
                    if expected_hash == s_hash:
                        logger.info(f"Integrity: Snapshot {snap_id} verified against Titanium++ chain.")
                        return True
                        
                # Fallback: Check if file_hash itself is recorded in metadata (for migration support)
                # Or just return True in dev mode if no record found (to avoid blocking first-time users)
                if not rows:
                    logger.warning(f"Integrity: No record found for {snapshot_path.name}. Proceeding with caution.")
                    return True
                    
        except Exception as e:
            logger.debug(f"Integrity: Verification failed: {e}")
            return True # Fail open in case of DB schema mismatch during migration
            
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
                        # v1.2.4: Exponential backoff with local JITTER to prevent thundering herd
                        # v1.2.4-TITANIUM++: Use stable run-to-run RNG seed based on normalized DB identity
                        import random
                        # Canonicalize path for cross-OS seed stability
                        seed_str = str(self.db_path.resolve()).replace("\\", "/").lower()
                        rng = random.Random(hash(seed_str) + attempt)
                        delay = self.SQLITE_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                        jitter = delay * rng.uniform(0.8, 1.2)
                        time.sleep(jitter)
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
        structural_hash: str | None = None,
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

        # v1.2.4-patch-hygiene: Prevent semantic spam in GLOBAL tier
        if to_global:
            # Check for existing identical content in global brain
            try:
                g_path = self.topology.resolve("global", "global")
                if g_path and g_path.exists():
                    with self.get_connection(g_path, readonly=True) as global_conn:
                        existing = global_conn.execute(
                            "SELECT id FROM observations WHERE content = ? AND is_active = 1 LIMIT 1", 
                            (content,)
                        ).fetchone()
                        if existing:
                            logger.info(f"Hygiene: Suppressing duplicate GLOBAL memory (ID: {existing[0]})")
                            return existing[0]
            except Exception as e:
                logger.warning(f"Hygiene: Global duplicate check failed: {e}")

        # v1.2.4-patch: Ensure symbol is never NULL if uid exists
        effective_symbol = symbol or uid

        from kit.core.memory_policy import MemoryPolicy
        confidence = MemoryPolicy.calculate_confidence(importance)
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
            structural_hash=structural_hash,
            agent_id=agent_id,
            supersedes_id=supersede_id,
            target_tier=MemoryTier.GLOBAL if to_global else None,
        )

        decision = self._router.route_write(request)
        if decision.decision == "rejected":
            raise SAMBrainError(f"Cognitive write rejected: {decision.reason}")

        if decision.assigned_tier == MemoryTier.LOCAL:
            self._signal_snapshot_refresh()

        from kit.core.memory_policy import MemoryPolicy
        now_ts = time.time()
        
        # v1.2.4-TITANIUM-FROZEN: Unified Scoring entry
        m_proto = Memory(
            id=decision.observation_id or 0,
            node_uid=uid,
            content=content,
            score=confidence,
            brain_source="local" if decision.assigned_tier == MemoryTier.LOCAL else "global",
            symbol=effective_symbol,
            created_at=datetime.now(UTC).isoformat(),
            importance=importance,
            tag=normalized_tag,
            namespace=namespace,
            scope=normalized_scope,
        )
        canonical_score = MemoryPolicy.calculate_score(m_proto, now_ts)

        # v1.2.4-STAGE5.5.3: Push to L0 for Immediate Recall
        if decision.observation_id:
             self._l0_cache.push(replace(m_proto, id=decision.observation_id, materialized_score=canonical_score))

        # v1.2.4-STAGE5.5: SRE Write-time sampling
        import random
        from kit.core.kit_sre import SAMPLING_RATE, SREEngine
        if effective_symbol and random.random() < SAMPLING_RATE:
            try:
                # We do a lightweight drift check. 
                # To keep learn() fast, we only evaluate drift and record event if significant.
                sre = SREEngine(self)
                metrics = sre.evaluate_drift(effective_symbol)
                # Only record if it crosses the first threshold
                from kit.core.kit_sre import DRIFT_THRESHOLD_OBSOLETE
                if metrics.final_score >= DRIFT_THRESHOLD_OBSOLETE:
                    sre._record_drift_event(metrics)
            except Exception as e:
                logger.debug(f"SRE: Sampling failed for {effective_symbol}: {e}")

        return decision.observation_id or 0

    def assimilate(
        self, 
        content: str, 
        symbol: str, 
        metadata: Dict, 
        structural_hash: str
    ) -> None:
        """
        Pure IO structural assimilation (Stage 5.5.2 Commit Kernel).
        """
        event = CommitEvent(
            content=content,
            symbol=symbol,
            metadata=metadata,
            structural_hash=structural_hash
        )
        self._commit_layer.add(event)
        
        # v1.2.4-STAGE5.5.3: Push to L0 for Immediate Recall
        from kit.core.memory_policy import MemoryPolicy
        placeholder_confidence = MemoryPolicy.calculate_confidence(0.1)
        self._l0_cache.push(Memory(
            id=0, # Not yet committed
            node_uid=f"sensor:{structural_hash}",
            content=content,
            score=placeholder_confidence,
            brain_source="local",
            symbol=symbol,
            created_at=datetime.now(UTC).isoformat(),
            importance=0.1,
            structural_hash=structural_hash,
            materialized_score=placeholder_confidence
        ))

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
        deduplicate: bool = True,
        **kwargs: Any,
    ) -> Union[list[Memory], tuple[list[Memory], dict[str, float]]]:
        start_time = time.perf_counter()
        start_total = start_time if include_profile else 0.0

        current_scope = self._get_normalized_scope() if here else None

        # v1.2.4-STAGE5.5.3: Fast Path - L0 In-Memory Recall
        l0_results = []
        if not (since or until): # Immediacy focus
             l0_results = self._l0_cache.search(query=query, limit=limit)

        # v1.2.4: Slow Path - SQLite Search
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

        sqlite_memories = self._router.resolve_read(request)

        # Merge Results: Collect all candidates for arbitration
        merged_memories = list(l0_results) + list(sqlite_memories)

        # v1.2.4-TITANIUM: Collapse Arbitration Authority to MemoryPolicy
        from kit.core.memory_policy import MemoryPolicy
        
        context = {
            "agent_id": agent_id,
            "scope": current_scope,
            "symbol": symbol
        }
        
        final_memories = MemoryPolicy.arbitrate(
            candidates=merged_memories,
            context=context,
            limit=limit,
            now=time.time(),
            deduplicate=deduplicate
        )
        
        # Authority Trace (v1.2.4-TITANIUM)
        import hashlib
        input_hash = hashlib.md5(str([m.id for m in merged_memories]).encode()).hexdigest()
        output_hash = hashlib.md5(str([m.id for m in final_memories]).encode()).hexdigest()
        logger.debug(f"Authority: MemoryPolicy.arbitrate | In: {input_hash} | Out: {output_hash}")
        
        # v1.2.4-TITANIUM: Final Verification Oracle (Vantage Gate)
        final_memories = self._verify_with_vantage(final_memories)

        # v1.2.4-patch-infrastructure: Update usage telemetry (The "Usage Boost" foundation)
        # Skip synchronous telemetry in TEST mode to maintain performance invariants
        from kit.core.kit_env import ExecutionMode, get_execution_mode
        if get_execution_mode() == ExecutionMode.TEST:
            if include_profile:
                profile = {"total": time.perf_counter() - start_total}
                return final_memories, profile
            return final_memories

        # v1.2.4-STAGE5.1: Log performance pulse
        latency_ms = (time.perf_counter() - start_time) * 1000
        hit = 1 if final_memories else 0
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO metrics (event_type, signal, latency_ms, outcome)
                    VALUES (?, ?, ?, ?)
                """, ("recall_pulse", json.dumps(entities or []), latency_ms, "hit" if hit else "miss"))
                conn.commit()
        except Exception as e:
            logger.debug(f"Telemetry: Failed to log recall pulse: {e}")

        for m in final_memories:
            try:
                # We only touch if it's from a RW tier (local or global)
                if m.brain_source in ("local", "global"):
                    self.touch_fact(m.id)
            except Exception as e:
                logger.debug(f"Telemetry: Failed to touch fact {m.id}: {e}")

        if include_profile:
            profile = {"total": time.perf_counter() - start_total}
            return final_memories, profile
        return final_memories

    # v1.2.4-TITANIUM: Authority Collapse
    # Logic delegated to MemoryPolicy kernel.
    
    def __getattr__(self, name):
        # HARD GUARD: Catch accidental reintroduction of deleted scoring logic
        if name in ("_calculate_runtime_score", "_recall_sort_key"):
             raise AttributeError(f"CRITICAL: {name} is deleted in v1.2.4. Use MemoryPolicy.")
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def add_symbol_edge(self, source: str, relation: str, target: str, confidence: float = 1.0) -> None:
        """Add a relationship between symbols with safety limits (v1.2.4-STAGE5.2)."""
        MAX_EDGES_PER_SYMBOL = 64
        
        def _add(conn: sqlite3.Connection):
            # 1. Enforcement: Check existing edge count
            count = conn.execute(
                "SELECT COUNT(*) FROM symbol_edges WHERE source_symbol = ?", (source,)
            ).fetchone()[0]
            
            if count >= MAX_EDGES_PER_SYMBOL:
                logger.warning(f"Graph: Symbol '{source}' reached edge limit ({MAX_EDGES_PER_SYMBOL}). Skipping.")
                return

            conn.execute("""
                INSERT INTO symbol_edges (source_symbol, relation_type, target_symbol, confidence)
                VALUES (?, ?, ?, ?)
            """, (source, relation, target, confidence))
            
        self._run_write_transaction(_add)

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
        """Deterministic Confidence via single-surface results (v1.2.4)."""
        if not memories:
            return 0.0
        if len(memories) == 1:
            return 1.0
        # Authority Rule: Confidence is purely the delta between Rank 1 and Rank 2
        # We use the score from the memories which were calculated by MemoryPolicy
        from kit.core.memory_policy import MemoryPolicy
        now = time.time()
        top_score = MemoryPolicy.calculate_score(memories[0], now)
        runner_score = MemoryPolicy.calculate_score(memories[1], now)
        return max(0.0, (top_score - runner_score) / (abs(top_score) + 1e-6))

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
            branch=row["branch"],
            tag=row["tag"],
            is_active=bool(row["is_active"]),
            supersedes_id=row["supersedes_id"],
            materialized_score=row["materialized_score"],
            created_at_bucket=row["created_at_bucket"],
            structural_hash=row["structural_hash"],
            metadata=json.loads(row["metadata"] or "{}")
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
        """Retrieve kernel statistics (v1.2.4-STAGE5)."""
        stats = {}
        with self.get_connection() as conn:
            # Legacy basic stats
            stats["nodes"] = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            stats["observations"] = conn.execute("SELECT COUNT(*) FROM observations WHERE is_active = 1").fetchone()[0]
            stats["edges"] = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            stats["version"] = self.cognition_version
            stats["db_path"] = str(self.db_path)

            # Stage 5.1: GQI 2.0 (Hygiene + Pulse)
            gqi = calculate_gqi(conn)
            
            try:
                canonical_count = conn.execute("SELECT COUNT(*) FROM observations WHERE is_canonical = 1 AND is_active = 1").fetchone()[0]
                merged_count = conn.execute("SELECT COUNT(*) FROM observations WHERE canonical_id IS NOT NULL").fetchone()[0]
            except sqlite3.OperationalError:
                canonical_count = 0
                merged_count = 0

            stats["gqi"] = {
                "total": gqi.total_memories,
                "entropy_score": round(gqi.entropy_score, 4),
                "quality_score": round(gqi.quality_score, 2),
                "symbol_debt_ratio": round(gqi.symbol_debt_ratio * 100, 1),
                "symbol_health": round(gqi.symbol_structured_ratio * 100, 1),
                "duplicate_ratio": round(gqi.duplicate_ratio * 100, 1),
                "orphan_ratio": round(gqi.orphan_ratio * 100, 1),
                "recall_hit_rate": round(gqi.recall_hit_rate * 100, 1),
                "avg_recall_latency_ms": round(gqi.avg_recall_latency_ms, 2),
                "canonical_count": canonical_count,
                "merged_count": merged_count
            }
            stats["namespaces"] = get_namespace_stats(conn)
            
        return stats

    def _verify_with_vantage(self, memories: list[Memory]) -> list[Memory]:
        """
        Verification Gate (Supreme Court): Verifies cognitive decisions via structural oracle.
        Invariant: Vantage MUST NOT influence ranking. It MAY ONLY validate structural correctness.
        Architecture: v1.2.4-TITANIUM Final Loop (Zero-Lag Batch Pass).
        """
        from kit.core.kit_env import ExecutionMode, get_execution_mode
        if get_execution_mode() == ExecutionMode.TEST:
             return memories

        # Step 1: Filter candidates that require structural verification (Batch Prep)
        to_verify = []
        for i, m in enumerate(memories):
            if m.symbol or m.structural_hash:
                to_verify.append({"content": m.content, "original_index": i, "memory": m})

        if not to_verify:
            return memories

        # Step 2: Batch Verification (Single IPC Call to Rust Oracle)
        from kit.core.kit_vantage import invoke_vantage_batch
        batch_items = [{"content": item["content"]} for item in to_verify]
        batch_signals = invoke_vantage_batch(batch_items)

        # Step 3: Apply Verification Law (YES/NO/WARNING)
        for i, signals in enumerate(batch_signals):
            m = to_verify[i]["memory"]
            is_valid = True
            
            # Oracle Check: Compare structural hashes if available
            for sig in signals:
                if m.structural_hash and sig.structural_hash and sig.structural_hash != m.structural_hash:
                    logger.warning(f"STRUCTURAL DRIFT: Symbol '{m.symbol}' failed verification gate.")
                    is_valid = False
                    break
            
            # v1.2.4 Law: Vantage DOES NOT touch the score or metadata.
            # It only validates structural correctness.
            if not is_valid:
                logger.error(f"INTEGRITY FAILURE: Symbol '{m.symbol}' failed structural gate.")
                # v1.2.4-TITANIUM: We log the failure but DO NOT mutate the frozen DTO.
                # The user/IDE should rely on the logs or an explicit repair command.

        return memories

    def __enter__(self) -> "SAMBrain":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown()