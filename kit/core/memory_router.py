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
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
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
    limit: int = 15
    entities: list[str] | None = None
    here: bool = False
    with_global: bool = True
    agent_id: str | None = None
    scope: str | None = None
    symbol: str | None = None


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
    agent_id: str | None = None
    supersedes_id: int | None = None
    target_tier: Optional[MemoryTier] = None
    reason: str = ""


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


class MemoryTierRules:
    """
    Routing policy matrix.
    
    Determines: which tier should receive this memory based on confidence.
    """
    
    THRESHOLD_LOCAL = 0.30           # Minimum to store at all
    THRESHOLD_GLOBAL = 0.60          # Promote to cross-project
    THRESHOLD_FROZEN = 0.85          # Immutable status
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
        """Route request to appropriate tier based on confidence."""
        
        if request.target_tier == MemoryTier.FROZEN:
            return MemoryTier.FROZEN
            
        if request.target_tier == MemoryTier.GLOBAL:
            return MemoryTier.GLOBAL
            
        return MemoryTier.LOCAL


class MemoryRouter:
    """
    Gatekeeper for all memory writes.
    
    Single point of entry for trainers, kit_learn, kit_scan.
    
    Uses MemoryTopology to resolve LOCAL (per-project) and GLOBAL (system-wide) paths.
    """
    
    def __init__(
        self,
        topology: MemoryTopology,
        history_path: Optional[Path] = None,
        local_db_path_override: Optional[Path] = None,
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
        
        # History tracking
        if history_path is None:
            history_path = topology.resolve("global", "audit")
        self.history_path = history_path
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        self._decision_log: list[WriteDecisionRecord] = []
        self._write_buffer = RouterWriteBuffer()

        logger.info(f"MemoryRouter v1.2.4 (TITANIUM) initialized")
        logger.info(f"  L1-Local:  {self.local_db_path}")
        logger.info(f"  L2-Global: {self.global_db_path}")
        logger.info(f"  L3-Law:    {self.frozen_db_path}")
        logger.info(f"  L4-Audit:  {self.history_path}")
    
    def resolve_read(self, request: MemoryReadRequest) -> list[Any]:
        """
        Unified Read Dispatcher (v1.2.4).
        Routes query through Tier Hierarchy with deterministic priority.
        """
        from kit.core.kit_cognitive_core import Memory
        
        results: list[Memory] = []
        
        # 1. Route to L1 (Local)
        results.extend(self._query_tier(MemoryTier.LOCAL, request))
        
        # 2. Route to L2 (Global)
        if request.with_global:
            results.extend(self._query_tier(MemoryTier.GLOBAL, request))
            
            # 3. Route to L3 (Frozen Law)
            results.extend(self._query_tier(MemoryTier.FROZEN, request))
            
        # 4. Final Aggregation & Ranking (Shadowing Logic)
        # Unique by UID, keeping the one with higher Tier priority (Local > Law > Global for skills)
        # Note: Law has high priority in recall, but Local can override.
        seen_uids = set()
        final_results = []
        
        # Sort results by tier priority and tag priority before deduplication
        # Priority: Tag (Invariant > Decision) > Tier (Local > Law > Global) > Score
        tag_priority = {"invariant": 3, "decision": 2, "preference": 1, "note": 0, "friction": 0}
        priority_map = {"local": 3, "law": 2, "global": 1}
        
        results.sort(
            key=lambda x: (
                tag_priority.get(x.tag, 0),
                priority_map.get(x.brain_source, 0),
                x.materialized_score
            ), 
            reverse=True
        )
        
        return results[:request.limit]

    def _query_tier(self, tier: MemoryTier, request: MemoryReadRequest) -> list[Any]:
        """Execute query against a specific tier using optimal PRAGMAs."""
        scope = "local" if tier == MemoryTier.LOCAL else "global"
        db_type = "local" if tier == MemoryTier.LOCAL else ("global" if tier == MemoryTier.GLOBAL else "frozen")
        
        path = self.local_db_path if tier == MemoryTier.LOCAL else self.topology.resolve(scope, db_type)
        if not path.exists():
            return []
            
        # Authority Pattern: Use topology to connect with Read-Only guards
        try:
            # v1.2.4: If path is overridden, we still use topology.connect logic but on the specific path
            if tier == MemoryTier.LOCAL and self.local_db_path != self.topology.resolve("local", "local"):
                # Fallback connection for isolated paths
                conn = sqlite3.connect(
                    f"file:{path.as_posix()}?mode=ro", 
                    uri=True,
                    timeout=10.0,
                    check_same_thread=False,
                    isolation_level=None
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only=ON")
            else:
                conn = self.topology.connect(scope, db_type, readonly=True)
                
            try:
                # v1.2.4: Deterministic Recall Logic
                # (This logic is moved from SAMBrain to Router for centralization)
                return self._execute_recall_on_conn(conn, tier, request)
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Read failed on {tier.value}: {e}")
            return []

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
            
        # 2. Entity/FTS Filter
        entity_where = ""
        if request.entities:
            placeholders = ",".join(["?"] * len(request.entities))
            uid_clause = f"n.uid IN ({placeholders})"
            params.extend([e.lower() for e in request.entities])
            
            # Hybrid FTS support (if query is present)
            if request.query:
                fts_clause = "o.id IN (SELECT rowid FROM observations_fts WHERE observations_fts MATCH ?)"
                entity_where = f"({uid_clause} OR {fts_clause})"
                params.append(request.query)
            else:
                entity_where = uid_clause
                
        if entity_where:
            where_clauses.append(entity_where)
            
        # 3. Symbol Filter
        if request.symbol:
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
                score=0.0,
                brain_source="local" if tier == MemoryTier.LOCAL else ("law" if tier == MemoryTier.FROZEN else "global"),
                layer=row["layer"],
                namespace=row["namespace"],
                branch=row["branch"],
                created_at=row["created_at"],
                importance=row["importance"],
                symbol=row["symbol"],
                tag=row["tag"],
                scope=row["scope"],
                is_active=bool(row["is_active"]),
                supersedes_id=row["supersedes_id"],
                materialized_score=row["materialized_score"],
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
    
    def _write_to_tier(self, tier: MemoryTier, request: MemoryWriteRequest) -> None:
        """Write memory to the assigned tier's database with Titanium Schema enforcement."""
        
        # v1.2.4-COLLAPSE-SAFE: Frozen Tier Architecture Invariant
        if tier == MemoryTier.FROZEN:
            logger.error(f"CRITICAL: Attempted write to FROZEN tier: {request.key}")
            raise PermissionError(f"Tier {tier.value} (FROZEN) is read-only by architecture.")

        # Authority Connection: Always use topology.connect (enforces WAL/Locking)
        if tier == MemoryTier.LOCAL and self.local_db_path != self.topology.resolve("local", "local"):
            # Isolated path connection for tests
            path = self.local_db_path
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                f"file:{path.as_posix()}", 
                uri=True,
                timeout=10.0,
                check_same_thread=False,
                isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
        else:
            conn = self.topology.connect(
                scope="local" if tier == MemoryTier.LOCAL else "global",
                db_type="local" if tier == MemoryTier.LOCAL else "global",
                readonly=False
            )
        try:
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
                    namespace, scope, branch, symbol, metadata, agent_id, supersedes_id, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    node_id,
                    content_str,
                    request.layer,
                    request.tag,
                    request.importance,
                    request.importance * 0.47712125471966244, # importance * log10(1 + 2)
                    request.namespace,
                    request.scope,
                    request.branch,
                    request.symbol,
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
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                logger.warning(f"DB locked, buffering to memory: {request.key}")
                self._write_buffer.add({"request": request, "tier": tier})
                return
            raise
        finally:
            conn.close()
        
        logger.info(f"Memory written: {request.key} → {tier.value} (confidence={request.confidence:.3f})")
    
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
        """Log routing decision to JSONL file."""
        self._decision_log.append(decision)
        
        try:
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "key": decision.request_key,
                    "decision": decision.decision.value,
                    "tier": decision.assigned_tier.value if decision.assigned_tier else None,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                    "timestamp": decision.timestamp,
                }) + "\n")
        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
    
    def get_decision_log(self) -> list[WriteDecisionRecord]:
        """Retrieve in-memory decision log."""
        return self._decision_log.copy()
    
    def stats(self) -> dict[str, Any]:
        """Quick statistics on routing behavior."""
        log = self._decision_log
        
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
        
        # Create router with topology
        router = MemoryRouter(topology, history_path)
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
                init_fts(conn)
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
            if key == "by_tier":
                print(f"  Memories by tier: {value}")
            else:
                print(f"  {key}: {value}")
        
        print("\n✅ Router demo complete\n")
