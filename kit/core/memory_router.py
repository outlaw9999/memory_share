# kit/core/memory_router.py
# v1.2.4 — Memory Router (Gatekeeper Layer)
#
# Philosophy:
#   SINGLE GATE for all memory writes.
#   All write requests must pass through this router.
#   Router applies rules, validates, and routes to appropriate tier.
#
# Critical Invariant:
#   trainer → router → DB (NEVER direct writes)
#
# ARCHITECTURE: Uses MemoryTopology to resolve GLOBAL and LOCAL paths
#   LOCAL is per-project: <project_root>/.kit/local_brain.db
#   GLOBAL is system-wide: ~/.kit/global_brain.db

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, replace, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from kit.coherence.coherence_engine import MemoryCoherenceEngine
from typing import Any, Optional

from kit.core.memory_topology import MemoryTopology, MemoryTopologyFactory

logger = logging.getLogger("kit.memory_router")


class MemoryTier(StrEnum):
    """Three-tier architecture (v1.2.4 FINAL)."""
    LOCAL = "local"           # Project-specific (local_brain.db)
    GLOBAL = "global"         # Cross-project (global_brain.db)
    FROZEN = "read_only"      # Immutable (global_read_only.db)


class WriteSource(StrEnum):
    """Authorized sources for memory writes."""
    TRAINER = "adaptive_trainer"
    KIT_LEARN = "kit_learn"
    KIT_SCAN = "kit_scan"


class WriteDecision(StrEnum):
    """Outcomes of routing decision."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CACHED = "cached"


@dataclass
class MemoryReadRequest:
    """Request to retrieve memory facts."""
    
    query: str
    limit: int = 10
    entities: list[str] | None = None
    here: bool = False
    with_global: bool = True
    agent_id: str | None = None
    scope: str | None = None
    symbol: str | None = None
    since: str | None = None          # ISO format date
    until: str | None = None          # ISO format date


@dataclass
class RecallTrace:
    """Telemetry and explainability for a recall request (v1.2.4-TITANIUM)."""
    cache_hit: bool = False
    satiety_reached: bool = False
    tiers_queried: list[str] = field(default_factory=list)
    tier_counts: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    trace_version: str = "v1.0"

@dataclass
class RecallResult:
    """Contract bundle for retrieval operations."""
    memories: list[Any]
    trace: RecallTrace
    version: str = "v1.2.4"



@dataclass
class MemoryWriteRequest:
    """Request to write/update a memory fact."""
    
    source: WriteSource
    key: str                           # Memory identifier (node uid)
    content: str | dict                # What to store (observation content)
    confidence: float                  # 0.0 to 1.0
    metadata: dict[str, Any]           # Context (symbol, frequency, etc.)
    node_type: str = "observation"
    tag: str = "decision"
    status: str = "active"
    visibility: str = "local"
    layer: str = "episodic"
    importance: float = 1.0
    namespace: str = "shared"
    scope: str = ""
    branch: str = "main"
    symbol: str | None = None
    structural_hash: str | None = None
    agent_id: str | None = None
    supersedes_id: int | None = None
    target_tier: Optional[MemoryTier] = None
    reason: str = ""
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WriteDecisionRecord:
    """Log of routing decision."""
    
    request_key: str
    decision: WriteDecision
    assigned_tier: Optional[MemoryTier]
    confidence: float
    reason: str
    timestamp: str
    observation_id: Optional[int] = None


class RouterWriteBuffer:
    """In-memory fallback when DB file is locked. (v1.2.4-COLLAPSE)"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._buffer: list[dict[str, Any]] = []

    def add(self, operation: dict[str, Any]) -> bool:
        if len(self._buffer) >= self.max_size:
            self._buffer.pop(0)
        self._buffer.append(operation)
        return True

    def flush(self) -> list[dict[str, Any]]:
        ops = self._buffer.copy()
        self._buffer.clear()
        return ops

    def is_empty(self) -> bool:
        return len(self._buffer) == 0


class RecallCache:
    """L0 In-Memory Cache for hot recall patterns (v1.2.4-TITANIUM Tuning)."""
    
    def __init__(self, max_size: int = 50, ttl_seconds: int = 30):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[datetime, list[Any]]] = {} # key -> (timestamp, results)
        self._lock = threading.Lock()
        self._trace: Optional[RecallTrace] = None

    def get(self, key: str) -> Optional[list[Any]]:
        with self._lock:
            if key in self._cache:
                ts, results = self._cache[key]
                if (datetime.now(UTC) - ts).total_seconds() < self.ttl:
                    return results
                del self._cache[key]
        return None

    def set(self, key: str, results: list[Any]) -> None:
        with self._lock:
            if len(self._cache) >= self.max_size:
                try:
                    oldest = min(self._cache.keys(), key=lambda k: self._cache[k][0])
                    del self._cache[oldest]
                except ValueError:
                    pass
            self._cache[key] = (datetime.now(UTC), results)

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()


class MemoryTierRules:
    """
    Routing policy matrix.
    
    Determines: which tier should receive this memory based on confidence.
    """
    
    THRESHOLD_LOCAL = 0.30           # Minimum to store at all
    THRESHOLD_GLOBAL = 0.60          # Promote to cross-project
    THRESHOLD_FROZEN = 0.95          # Immutable status
    MAX_ERROR_RATE = 0.10            # If error_rate > 10%, reject
    MIN_FREQUENCY = 1
    
    @classmethod
    def validate_request(cls, request: MemoryWriteRequest) -> tuple[bool, str]:
        """Safety validation before routing."""
        
        # Check confidence in valid range
        if not (0.0 <= request.confidence <= 1.0):
            return False, f"confidence out of range: {request.confidence}"
        
        # Check minimum confidence to store
        if request.confidence < cls.THRESHOLD_LOCAL:
            return False, f"confidence {request.confidence} below LOCAL threshold {cls.THRESHOLD_LOCAL}"
        
        # Check metadata for error signals
        if "error_rate" in request.metadata:
            error_rate = request.metadata["error_rate"]
            if error_rate > cls.MAX_ERROR_RATE:
                return False, f"error_rate {error_rate} exceeds maximum {cls.MAX_ERROR_RATE}"
        
        # Check frequency
        if "frequency" in request.metadata:
            freq = request.metadata["frequency"]
            if freq < cls.MIN_FREQUENCY:
                return False, f"frequency {freq} below minimum {cls.MIN_FREQUENCY}"
        
        return True, ""
    
    @classmethod
    def route_to_tier(cls, request: MemoryWriteRequest) -> MemoryTier:
        """Route request to appropriate tier based on confidence (v1.2.4-TITANIUM)."""
        
        # 1. Direct override (Expert/Governance mode)
        if request.target_tier:
            return request.target_tier
            
        # 2. Confidence-based routing
        if request.confidence >= cls.THRESHOLD_FROZEN:
            return MemoryTier.FROZEN
            
        if request.confidence >= cls.THRESHOLD_GLOBAL:
            return MemoryTier.GLOBAL
            
        return MemoryTier.LOCAL


class MemoryRouter:
    """
    Gatekeeper for all memory writes.
    
    Single point of entry for trainers, kit_learn, kit_scan.
    
    Uses MemoryTopology to resolve LOCAL (per-project) and GLOBAL (system-wide) paths.
    """
    
    DEFAULT_RECENT_LIMIT = 5
    
    def __init__(
        self,
        topology: MemoryTopology,
        history_path: Optional[Path] = None,
        local_db_path_override: Optional[Path] = None,
        connection_provider: Optional[Callable] = None,
        closer: Optional[Callable] = None,
    ):
        """
        Initialize router with topology context.
        
        Args:
            topology: MemoryTopology instance (defines where memories live)
            history_path: Optional path to routing decision log
                         If None, uses topology.resolve("global", "audit")
        """
        self.topology = topology
        
        # Resolve database paths using topology
        self.local_db_path = local_db_path_override or topology.resolve("local", "local")
        self.global_db_path = topology.resolve("global", "global")
        self.frozen_db_path = topology.resolve("global", "frozen")
        
        # v1.2.5: Identity-based lifecycle management
        if connection_provider:
            self._connection_provider = connection_provider
            self._owns_connection = False
        else:
            # Default provider: Router owns these connections
            def default_provider(path, readonly=False):
                conn = sqlite3.connect(path)
                conn.row_factory = sqlite3.Row
                return conn
            self._connection_provider = default_provider
            self._owns_connection = True
        
        # History tracking
        if history_path is None:
            history_path = topology.resolve("global", "audit")
        self.history_path = history_path
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        self._decision_log: list[WriteDecisionRecord] = []
        self._decision_lock = threading.Lock()
        self._write_buffer = RouterWriteBuffer()
        self._recall_cache = RecallCache()
        self._coherence = MemoryCoherenceEngine()
        self._closer = closer
        self._owns_connection = False # v1.2.5: Track ownership for lifecycle safety

        logger.info(f"MemoryRouter v1.2.4 (TITANIUM) initialized")
        
        # v1.2.4: Dedicated Log Sink (Disabled in TEST mode to prevent WinError 32)
        from kit.core.kit_env import ExecutionMode, get_execution_mode
        if get_execution_mode() != ExecutionMode.TEST:
            try:
                log_dir = self.history_path.parent / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                fh = logging.FileHandler(log_dir / "router.log", encoding="utf-8")
                fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                logger.addHandler(fh)
            except Exception:
                pass

        logger.info(f"  L1-Local:  {self.local_db_path}")
        logger.info(f"  L2-Global: {self.global_db_path}")
        logger.info(f"  L3-Law:    {self.frozen_db_path}")
        logger.info(f"  L4-Audit:  {self.history_path}")

    def close(self):
        """Release system resources (v1.2.4-TITANIUM)."""
        if self._closer:
            try:
                self._closer()
            except Exception:
                pass
        
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                logger.removeHandler(handler)

    def _pick(self, rows: list[dict], query: str = None) -> Any:
        if not rows:
            return None
        from kit.core.kit_cognitive_core import Memory
        # Hydrate the best row
        best_row = max(rows, key=lambda r: r.get("materialized_score", 0.0))
        return self._hydrate_memory(best_row)

    def _generate_cache_key(self, request: MemoryReadRequest) -> str:
        """Normalized semantic cache key (v1.2.4-TITANIUM)."""
        q = (request.query or "").lower().strip()
        s = (request.scope or "").strip("/")
        e = ",".join(sorted(request.entities)) if request.entities else ""
        # Bucketing limit (5, 10, 25, 50, 100)
        l = 5 if request.limit <= 5 else (10 if request.limit <= 10 else (25 if request.limit <= 25 else (50 if request.limit <= 50 else 100)))
        return f"q:{q}|s:{s}|e:{e}|l:{l}|sym:{request.symbol}|here:{request.here}"
    
    def resolve_read(self, request: MemoryReadRequest, return_mode: str = "legacy") -> Any:
        """
        Unified Read Dispatcher (v1.2.4-TITANIUM Stabilized).
        Routes query through L0 Cache -> Soft-Satiety Progressive Recall.
        """
        from kit.core.kit_cognitive_core import Memory
        import time
        
        start_time = time.perf_counter()
        trace = RecallTrace()
        
        # --- Stage 0: L0 Cache Hit (Normalized) ---
        cache_key = self._generate_cache_key(request)
        cached_hit = self._recall_cache.get(cache_key)
        if cached_hit:
            trace.cache_hit = True
            trace.latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"L0 Cache Hit: {cache_key[:60]}")
            return cached_hit

        raw_results: list[dict] = []
        final_limit = request.limit
        
        # --- Stage 1: Local Tier (Primary Context) ---
        local_rows = self._query_tier_raw(MemoryTier.LOCAL, request)
        raw_results.extend(local_rows)
        trace.tiers_queried.append("local")
        trace.tier_counts["local"] = len(local_rows)
        
        # --- Stage 2: Satiety Assessment (Soft-Skip) ---
        SATIETY_THRESHOLD = 0.85
        high_conf_local = [r for r in local_rows if r["materialized_score"] >= SATIETY_THRESHOLD]
        
        # Bounded Global Fetch: Even if local is enough, we fetch a minimal global set 
        # to ensure semantic overrides aren't missed (Safety Boundary).
        global_limit = 2 if len(high_conf_local) >= final_limit else request.limit
        if len(high_conf_local) >= final_limit:
            trace.satiety_reached = True
            
        # --- Stage 3: Global Tiers (Scoped) ---
        if request.with_global:
            # Create a deprioritized request for global tiers if local is satiated
            global_request = replace(request, limit=global_limit) if trace.satiety_reached else request
            
            for tier in [MemoryTier.GLOBAL, MemoryTier.FROZEN]:
                rows = self._query_tier_raw(tier, global_request)
                raw_results.extend(rows)
                trace.tiers_queried.append(tier.value)
                trace.tier_counts[tier.value] = len(rows)

        logger.debug(f"Recall: Stage 3 complete. raw_results count: {len(raw_results)}")

        # --- Stage 4: Progressive Fallback (Fuzzy/FTS) ---
        if not raw_results and request.entities and not request.query:
            logger.info(f"Recall: No direct hits for {request.entities}. Falling back to fuzzy FTS search.")
            # Build a fuzzy query from entities
            fuzzy_query = " OR ".join(request.entities)
            
            # Use query instead of entities to trigger FTS5
            relaxed_request = replace(request, entities=None, query=fuzzy_query)
            for tier in [MemoryTier.LOCAL, MemoryTier.GLOBAL, MemoryTier.FROZEN]:
                rows = self._query_tier_raw(tier, relaxed_request)
                raw_results.extend(rows)
            
            logger.debug(f"Recall: Fuzzy fallback found {len(raw_results)} rows.")

        # --- Stage 4.5: Recent Fallback (Last Resort) ---
        if not raw_results:
            logger.info("Recall: Sparse result set. Activating RECENT fallback.")
            relaxed_request = replace(request, entities=None, query=None, limit=self.DEFAULT_RECENT_LIMIT, symbol=None)
            final_limit = self.DEFAULT_RECENT_LIMIT
            
            for tier in [MemoryTier.FROZEN, MemoryTier.GLOBAL, MemoryTier.LOCAL]:
                rows = self._query_tier_raw(tier, relaxed_request)
                raw_results.extend(rows)
                trace.tier_counts[f"fallback_{tier.value}"] = len(rows)
            logger.debug(f"Recall: Recent fallback found {len(raw_results)} rows.")


        # --- Stage 5: Finalize & Hydrate Candidates (v1.2.4-TITANIUM Purity) ---
        # The router no longer ranks or scores. It returns hydrated candidates 
        # for the Core to arbitrate via MemoryPolicy.
        final_memories = [self._hydrate_memory(r) for r in raw_results]
        
        # --- Stage 6: Finalize Trace & Cache ---
        trace.latency_ms = (time.perf_counter() - start_time) * 1000
        self._recall_cache.set(cache_key, final_memories)
        
        # Router Trace (v1.2.4-TITANIUM)
        logger.debug(f"Router: Recall complete | Tiers: {trace.tiers_queried} | Count: {len(final_memories)}")

        if return_mode == "contract":
            from kit.core.memory_router import RecallResult
            return RecallResult(memories=final_memories, trace=trace)
        return final_memories


    def _query_tier_raw(self, tier: MemoryTier, request: MemoryReadRequest) -> list[dict]:
        """Execute query and return raw rows (v1.2.4-TITANIUM Tuning)."""
        scope = "local" if tier == MemoryTier.LOCAL else "global"
        db_type = "local" if tier == MemoryTier.LOCAL else ("global" if tier == MemoryTier.GLOBAL else "frozen")
        
        path = self.local_db_path if tier == MemoryTier.LOCAL else self.topology.resolve(scope, db_type)
        if not path.exists():
            return []
            
        if not self._connection_provider:
            raise RuntimeError("MemoryRouter requires a connection provider.")

        conn = None
        try:
            # Authority Connection
            conn = self._connection_provider(path, readonly=True)
            
            # v1.2.4-TITANIUM: Robust handle enforcement
            # Ensure we are working with a raw connection or a wrapper
            # If it's a context manager (like SAMBrain.get_connection), we enter it
            if hasattr(conn, "__enter__"):
                with conn as managed_conn:
                    managed_conn.row_factory = sqlite3.Row
                    return self._execute_recall_on_conn_raw(managed_conn, tier, request)
            else:
                # Direct connection from provider (like lambda in Factory)
                conn.row_factory = sqlite3.Row
                return self._execute_recall_on_conn_raw(conn, tier, request)
        except Exception as e:
            logger.error(f"Raw Read failed on {tier.value}: {e}")
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _execute_recall_on_conn_raw(self, conn: sqlite3.Connection, tier: MemoryTier, request: MemoryReadRequest) -> list[dict]:
        """Low-level row fetcher (v1.2.4-TITANIUM Tuning)."""
        current_branch = "main"
        where_clauses = ["o.is_active = 1", "o.branch = ?"]
        params = [current_branch]
        
        if request.scope:
            parts = request.scope.split("/") if request.scope else []
            scopes = ["/".join(parts[:i]) for i in range(len(parts) + 1)]
            placeholders = ",".join(["?"] * len(scopes))
            where_clauses.append(f"(o.scope IN ({placeholders}) OR o.scope = '')")
            params.extend(scopes)
            
        if request.since:
            where_clauses.append("o.created_at >= ?")
            params.append(request.since)
        if request.until:
            where_clauses.append("o.created_at <= ?")
            params.append(request.until)

        entity_where = ""
        if request.entities or request.query:
            symbol_clause = ""
            if request.entities:
                placeholders = ",".join(["?"] * len(request.entities))
                if request.symbol:
                     where_clauses.append("o.symbol = ?")
                     params.append(request.symbol)
                else:
                    symbol_clause = f"(o.symbol IN ({placeholders}) OR n.uid IN ({placeholders}))"
                    params.extend(request.entities)
                    params.extend(request.entities)
            
            if request.query and not request.symbol:
                fts_clause = "o.id IN (SELECT rowid FROM observations_fts WHERE observations_fts MATCH ?)"
                if symbol_clause:
                    entity_where = f"({symbol_clause} OR {fts_clause})"
                else:
                    entity_where = fts_clause
                params.append(request.query)
            elif symbol_clause:
                entity_where = symbol_clause
                
        if entity_where:
            where_clauses.append(entity_where)
            
        if request.symbol and not request.entities and not request.query:
            where_clauses.append("o.symbol = ?")
            params.append(request.symbol)
            
        sql = f"""
        SELECT o.*, n.uid as node_uid
        FROM observations o
        JOIN nodes n ON o.node_id = n.id
        WHERE {" AND ".join(where_clauses)}
        ORDER BY o.materialized_score DESC, o.created_at DESC
        LIMIT ?
        """
        params.append(request.limit * 2)
        
        cur = conn.execute(sql, params)
        logger.debug(f"SQL Execute: {sql} | Params: {params}")
        rows = [dict(r) for r in cur.fetchall()]
        logger.debug(f"SQL Found: {len(rows)} rows.")
        
        # Inject metadata for sorting
        brain_source = "local" if tier == MemoryTier.LOCAL else ("law" if tier == MemoryTier.FROZEN else "global")
        for r in rows:
            r["brain_source"] = brain_source
            
        return rows

    def _hydrate_memory(self, row: dict) -> Any:
        """Lazy hydration factory (v1.2.4-TITANIUM-FROZEN)."""
        from kit.core.kit_cognitive_core import Memory
        return Memory(
            id=row["id"],
            node_uid=row["node_uid"],
            content=row["content"],
            score=row.get("score", row.get("materialized_score", 0.5)),
            brain_source=row["brain_source"],
            layer=row["layer"],
            namespace=row["namespace"],
            branch=row["branch"],
            created_at=row["created_at"],
            created_at_bucket=row["created_at_bucket"] if "created_at_bucket" in row else 0,
            importance=row["importance"],
            symbol=row["symbol"],
            tag=row["tag"],
            scope=row["scope"],
            is_active=bool(row["is_active"]),
            supersedes_id=row["supersedes_id"],
            materialized_score=row.get("materialized_score", 0.0),
            metadata=json.loads(row["metadata"] or "{}") if isinstance(row.get("metadata"), str) else (row.get("metadata") or {})
        )

    def _query_tier(self, tier: MemoryTier, request: MemoryReadRequest) -> list[Any]:
        """Legacy hydrated query (v1.2.4-patch)."""

    def _execute_recall_on_conn(self, conn: sqlite3.Connection, tier: MemoryTier, request: MemoryReadRequest) -> list[Any]:
        """Internal low-level query executor (Unified v1.2.4-TITANIUM)."""
        from kit.core.kit_cognitive_core import Memory
        
        current_branch = "main" # TODO: Support branching in Router
        
        where_clauses = ["o.is_active = 1", "o.branch = ?"]
        params = [current_branch]
        
        # 1. Scope Filter (Hierarchy)
        if request.scope:
            parts = request.scope.split("/") if request.scope else []
            scopes = ["/".join(parts[:i]) for i in range(len(parts) + 1)]
            placeholders = ",".join(["?"] * len(scopes))
            where_clauses.append(f"(o.scope IN ({placeholders}) OR o.scope = '')")
            params.extend(scopes)
            
        # 2. Temporal Filter (v1.2.4-TITANIUM)
        if request.since:
            where_clauses.append("o.created_at >= ?")
            params.append(request.since)
        if request.until:
            where_clauses.append("o.created_at <= ?")
            params.append(request.until)

        # 3. Entity/FTS Filter (v1.2.4-TITANIUM SSOT)
        entity_where = ""
        if request.entities or request.query:
            symbol_clause = ""
            if request.entities:
                placeholders = ",".join(["?"] * len(request.entities))
                if request.symbol:
                     where_clauses.append("o.symbol = ?")
                     params.append(request.symbol)
                else:
                    symbol_clause = f"(o.symbol IN ({placeholders}) OR n.uid IN ({placeholders}))"
                    params.extend(request.entities)
                    params.extend(request.entities)
            
            if request.query and not request.symbol:
                fts_clause = "o.id IN (SELECT rowid FROM observations_fts WHERE observations_fts MATCH ?)"
                if symbol_clause:
                    entity_where = f"({symbol_clause} OR {fts_clause})"
                else:
                    entity_where = fts_clause
                params.append(request.query)
            elif symbol_clause:
                entity_where = symbol_clause
                
        if entity_where:
            where_clauses.append(entity_where)
            
        # 4. Symbol Filter (only if no entities and no query were provided)
        if request.symbol and not request.entities and not request.query:
            where_clauses.append("o.symbol = ?")
            params.append(request.symbol)
            
        sql = f"""
        SELECT o.*, n.uid as node_uid
        FROM observations o
        JOIN nodes n ON o.node_id = n.id
        WHERE {" AND ".join(where_clauses)}
        ORDER BY o.materialized_score DESC, o.created_at DESC
        LIMIT ?
        """
        params.append(request.limit * 2) # Overfetch for router-level merging
        
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        
        memories = []
        for row in rows:
            m = Memory(
                id=row["id"],
                node_uid=row["node_uid"],
                content=row["content"],
                score=row["materialized_score"],
                brain_source="local" if tier == MemoryTier.LOCAL else ("law" if tier == MemoryTier.FROZEN else "global"),
                layer=row["layer"],
                namespace=row["namespace"],
                branch=row["branch"],
                created_at=row["created_at"],
                created_at_bucket=row["created_at_bucket"] if "created_at_bucket" in row.keys() else 0,
                importance=row["importance"],
                symbol=row["symbol"],
                tag=row["tag"],
                scope=row["scope"],
                is_active=bool(row["is_active"]),
                supersedes_id=row["supersedes_id"],
                materialized_score=row["materialized_score"],
                metadata=json.loads(row["metadata"] or "{}") if isinstance(row.get("metadata"), str) else (row.get("metadata") or {})
            )
            memories.append(m)
            
        return memories

    def route_write(self, request: MemoryWriteRequest) -> WriteDecisionRecord:
        """Main entry point: validate + route memory write."""
        
        # Step 1: Validate request
        is_valid, validation_reason = MemoryTierRules.validate_request(request)
        if not is_valid:
            decision = WriteDecisionRecord(
                request_key=request.key,
                decision=WriteDecision.REJECTED,
                assigned_tier=None,
                confidence=request.confidence,
                reason=f"Validation failed: {validation_reason}",
                timestamp=datetime.now(UTC).isoformat(),
            )
            self._record_decision(decision)
            return decision
        
        # Step 2: Route to tier
        assigned_tier = MemoryTierRules.route_to_tier(request)
        
        # Step 3: Execute write
        try:
            obs_id = self._write_to_tier(assigned_tier, request)
            decision = WriteDecisionRecord(
                request_key=request.key,
                decision=WriteDecision.ACCEPTED,
                assigned_tier=assigned_tier,
                confidence=request.confidence,
                reason=f"Accepted to {assigned_tier.value}",
                timestamp=datetime.now(UTC).isoformat(),
                observation_id=obs_id
            )
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"Write failed for {request.key}: {e}")
            decision = WriteDecisionRecord(
                request_key=request.key,
                decision=WriteDecision.REJECTED,
                assigned_tier=assigned_tier,
                confidence=request.confidence,
                reason=f"Write failed: {str(e)}",
                timestamp=datetime.now(UTC).isoformat(),
            )
        
        # Step 4: Log decision
        self._record_decision(decision)
        
        return decision
    
    def _write_to_tier(self, tier: MemoryTier, request: MemoryWriteRequest) -> int:
        """Write memory to the assigned tier's database with Titanium Schema enforcement."""
        
        # v1.2.4-COLLAPSE-SAFE: Frozen Tier Architecture Invariant
        if tier == MemoryTier.FROZEN:
            logger.error(f"CRITICAL: Attempted write to FROZEN tier: {request.key}")
            raise PermissionError(f"Tier {tier.value} (FROZEN) is read-only by architecture.")

        # v1.2.4-TITANIUM: Logical Seal enforcement for L1
        if tier == MemoryTier.LOCAL:
            from kit.core.kit_lock import is_sealed
            if self.topology.project_root and is_sealed(self.topology.project_root):
                raise PermissionError("Memory kernel is sealed. Run 'kit unseal --reason <msg>' to continue learning.")

        # Authority Connection: Always use provider (enforces WAL/Locking)
        scope = "local" if tier == MemoryTier.LOCAL else "global"
        db_type = "local" if tier == MemoryTier.LOCAL else "global"
        
        path = self.local_db_path if tier == MemoryTier.LOCAL else self.topology.resolve(scope, db_type)

        if not self._connection_provider:
            raise RuntimeError("MemoryRouter requires a connection provider (SAMBrain authority).")

        conn = None
        try:
            conn = self._connection_provider(path, readonly=False)

            if hasattr(conn, "__enter__"):
                with conn as managed_conn:
                    return self._execute_write_on_conn(managed_conn, request)
            else:
                return self._execute_write_on_conn(conn, request)
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                logger.warning(f"DB locked, buffering to memory: {request.key}")
                self._write_buffer.add({"request": request, "tier": tier})
                return 0
            raise
        finally:
            # v1.2.5: Only close if the router owns the connection lifecycle
            if conn and self._owns_connection:
                try:
                    conn.close()
                except Exception:
                    pass

    def _execute_write_on_conn(self, conn: sqlite3.Connection, request: MemoryWriteRequest) -> int:
        """Internal low-level write executor (Titanium v1.2.4)."""
        # 1. Prepare Node Data
        node_uid = request.key.lower()
        content_str = json.dumps(request.content) if isinstance(request.content, dict) else request.content
        
        conn.execute("BEGIN IMMEDIATE")
        
        # 2. Upsert Node
        conn.execute(
            """INSERT INTO nodes (uid, node_type, status, visibility) 
               VALUES (?, ?, ?, ?) 
               ON CONFLICT(uid) DO UPDATE SET 
                 node_type=excluded.node_type,
                 status=excluded.status,
                 visibility=excluded.visibility""",
            (node_uid, request.node_type, request.status, request.visibility),
        )
        node_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", (node_uid,)).fetchone()
        node_id = node_row["id"]
        
        # 3. Handle Superseding (Inactivate old memory)
        if request.supersedes_id:
            conn.execute(
                "UPDATE observations SET is_active = 0, superseded_at = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), request.supersedes_id),
            )

        # 4. Insert Observation
        cur = conn.execute(
            """INSERT INTO observations 
               (node_id, content, layer, tag, importance, materialized_score, 
                namespace, scope, branch, symbol, structural_hash, metadata, agent_id, supersedes_id, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node_id,
                content_str,
                request.layer,
                request.tag,
                request.importance,
                request.importance * (2.0 / 6.0),
                request.namespace,
                request.scope,
                request.branch,
                request.symbol,
                request.structural_hash,
                json.dumps(request.metadata),
                request.agent_id,
                request.supersedes_id,
                1 # is_active
            ),
        )
        obs_id = cur.lastrowid
        
        # 4. Update FTS
        conn.execute("INSERT INTO observations_fts(rowid, content) VALUES (?, ?)", (obs_id, content_str))
        
        conn.commit()
        return obs_id
    
    def _get_db_path_for_tier(self, tier: MemoryTier) -> Path:
        """Map tier → database path."""
        
        if tier == MemoryTier.LOCAL:
            return self.local_db_path
        elif tier == MemoryTier.GLOBAL:
            return self.global_db_path
        elif tier == MemoryTier.FROZEN:
            return self.frozen_db_path
        else:
            raise ValueError(f"Unknown tier: {tier}")
    
    def _record_decision(self, decision: WriteDecisionRecord) -> None:
        """Log decision to memory and persistent history."""
        with self._decision_lock:
            self._decision_log.append(decision)
            try:
                # v1.2.4: Atomic history write within lock
                with open(self.history_path, "a", encoding="utf-8") as f:
                    from dataclasses import asdict
                    import json
                    f.write(json.dumps(asdict(decision)) + "\n")
            except Exception as e:
                logger.error(f"Failed to write routing history: {e}")
    
    def get_decision_log(self) -> list[WriteDecisionRecord]:
        """Retrieve in-memory decision log."""
        return self._decision_log.copy()
    
    def stats(self) -> dict[str, Any]:
        """Quick statistics on routing behavior."""
        with self._decision_lock:
            log = self._decision_log.copy()
        
        accepted = sum(1 for d in log if d.decision == WriteDecision.ACCEPTED)
        rejected = sum(1 for d in log if d.decision == WriteDecision.REJECTED)
        
        by_tier = {}
        for tier in MemoryTier:
            count = sum(1 for d in log if d.assigned_tier == tier and d.decision == WriteDecision.ACCEPTED)
            by_tier[tier.value] = count
        
        avg_confidence = (
            sum(d.confidence for d in log if d.decision == WriteDecision.ACCEPTED) / accepted
            if accepted > 0
            else 0.0
        )
        
        return {
            "total_requests": len(log),
            "accepted": accepted,
            "rejected": rejected,
            "by_tier": by_tier,
            "avg_confidence": avg_confidence,
        }


class MemoryRouterFactory:
    """Create router instances with proper initialization."""
    
    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        content TEXT NOT NULL,
        confidence REAL NOT NULL,
        metadata TEXT,
        source TEXT,
        tier TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_memory_key ON memory(key);
    CREATE INDEX IF NOT EXISTS idx_memory_tier ON memory(tier);
    CREATE INDEX IF NOT EXISTS idx_memory_confidence ON memory(confidence DESC);
    """
    
    @classmethod
    def create(cls, project_root: Path, history_path: Optional[Path] = None) -> MemoryRouter:
        """
        Create router and initialize all databases.
        
        Args:
            project_root: Path to project directory (for LOCAL scope)
            history_path: Optional path to routing decision log
        
        Returns:
            Initialized MemoryRouter with topology context
        """
        # Create topology for this project
        topology = MemoryTopologyFactory.for_project(project_root)
        
        # Initialize LOCAL scope databases
        cls._initialize_scope(topology, "local")
        
        # Initialize GLOBAL scope databases
        # (even if project_root is different, GLOBAL is shared)
        cls._initialize_scope(topology, "global")
        
        # Initialize SAMBrain for authority connection (v1.2.4)
        from kit.core.kit_cognitive_core import SAMBrain
        brain = SAMBrain(topology.resolve("local", "local"), root_path=project_root)
        
        # Create router with topology
        # v1.2.4: Provide default connection authority via SAMBrain
        router = MemoryRouter(
            topology, 
            history_path, 
            connection_provider=brain.get_connection,
            closer=brain.shutdown
        )
        logger.info(f"MemoryRouter created with topology for project: {project_root}")
        
        return router
    
    @classmethod
    def _initialize_scope(cls, topology: MemoryTopology, scope: str) -> None:
        """Initialize all databases in a given scope using central schema factory."""
        from kit.core.schema_factory import init_db, enable_wal
        
        db_types = ["local", "global", "frozen"]
        
        for db_type in db_types:
            # Skip local/global/frozen that don't belong to this scope
            if scope == "local" and db_type in ["global", "frozen"]:
                continue
            if scope == "global" and db_type == "local":
                continue
            
            db_path = topology.resolve(scope, db_type)
            if db_path is None:
                continue

            # Authority Connection
            # v1.2.4: Always use RW for initialization
            conn = topology.connect(scope, db_type, readonly=False)
            try:
                conn.execute("BEGIN IMMEDIATE")
                init_db(conn)
                enable_wal(conn)
                conn.commit()
                logger.debug(f"Initialized standardized schema and FTS for {scope}/{db_type}")
            finally:
                conn.close()


if __name__ == "__main__":
    import tempfile
    
    print("\n" + "="*70)
    print("🧠 KIT v1.2.4 Memory Router - Demonstration")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        kit_home = Path(tmpdir)
        router = MemoryRouterFactory.create(kit_home)
        
        # Example 1: High-confidence memory
        print("\n📝 Example 1: High-confidence memory (trainer)")
        req1 = MemoryWriteRequest(
            source=WriteSource.TRAINER,
            key="pattern:auth_middleware",
            content={"name": "Authentication Middleware", "frequency": 5},
            confidence=0.75,
            metadata={"frequency": 5, "success_rate": 0.9},
            reason="Detected auth pattern across projects",
        )
        decision1 = router.route_write(req1)
        print(f"  Decision: {decision1.decision.value}")
        print(f"  Assigned tier: {decision1.assigned_tier}")
        
        # Example 2: Low confidence (rejected)
        print("\n❌ Example 2: Low-confidence memory (rejected)")
        req2 = MemoryWriteRequest(
            source=WriteSource.TRAINER,
            key="pattern:random_code",
            content={"data": "stuff"},
            confidence=0.15,
            metadata={"frequency": 1},
            reason="One-off observation",
        )
        decision2 = router.route_write(req2)
        print(f"  Decision: {decision2.decision.value}")
        
        # Example 3: Very high confidence (frozen)
        print("\n🔒 Example 3: Expert knowledge (frozen tier)")
        req3 = MemoryWriteRequest(
            source=WriteSource.KIT_SCAN,
            key="best_practice:json_parsing",
            content={"rule": "Always validate JSON schema first"},
            confidence=0.92,
            metadata={"frequency": 100, "success_rate": 0.99},
            reason="Validated best practice across 20+ projects",
        )
        decision3 = router.route_write(req3)
        print(f"  Decision: {decision3.decision.value}")
        print(f"  Assigned tier: {decision3.assigned_tier}")
        
        # Show statistics
        print("\n📊 Router Statistics:")
        stats = router.stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n✅ Router demo complete\n")
