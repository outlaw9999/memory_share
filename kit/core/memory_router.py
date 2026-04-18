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


@dataclass
class MemoryWriteRequest:
    """Request to write/update a memory fact."""
    
    source: WriteSource
    key: str                           # Memory identifier
    content: str | dict                # What to store
    confidence: float                  # 0.0 to 1.0
    metadata: dict[str, Any]           # Context (symbol, frequency, etc.)
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
        
        if request.confidence >= cls.THRESHOLD_FROZEN:
            return MemoryTier.FROZEN
        elif request.confidence >= cls.THRESHOLD_GLOBAL:
            return MemoryTier.GLOBAL
        elif request.confidence >= cls.THRESHOLD_LOCAL:
            return MemoryTier.LOCAL
        else:
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
        self.local_db_path = topology.resolve("local", "local")
        self.global_db_path = topology.resolve("global", "global")
        self.frozen_db_path = topology.resolve("global", "frozen")
        
        # History tracking
        if history_path is None:
            history_path = topology.resolve("global", "audit")
        self.history_path = history_path
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        self._decision_log: list[WriteDecisionRecord] = []
        self._write_buffer = RouterWriteBuffer()

        logger.info(f"MemoryRouter initialized with topology authority")
        logger.info(f"  LOCAL: {self.local_db_path}")
        logger.info(f"  GLOBAL: {self.global_db_path}")
        logger.info(f"  FROZEN: {self.frozen_db_path}")
        logger.info(f"  History: {self.history_path}")
    
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
            self._write_to_tier(assigned_tier, request)
            decision = WriteDecisionRecord(
                request_key=request.key,
                decision=WriteDecision.ACCEPTED,
                assigned_tier=assigned_tier,
                confidence=request.confidence,
                reason=f"Accepted to {assigned_tier.value}",
                timestamp=datetime.now(UTC).isoformat(),
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
        """Write memory to the assigned tier's database."""
        
        # v1.2.4-COLLAPSE-SAFE: Frozen Tier Architecture Invariant
        if tier == MemoryTier.FROZEN:
            logger.error(f"CRITICAL: Attempted write to FROZEN tier: {request.key}")
            raise PermissionError(f"Tier {tier.value} (FROZEN) is read-only by architecture.")

        db_path = self._get_db_path_for_tier(tier)

        # Serialize content if dict
        content_str = json.dumps(request.content) if isinstance(request.content, dict) else request.content

        # Authority Pattern: Use topology to connect
        conn = self.topology.connect(
            scope="local" if tier == MemoryTier.LOCAL else "global",
            db_type=tier.value
        )
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR REPLACE INTO memory (key, content, confidence, metadata, source, tier, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.key,
                    content_str,
                    request.confidence,
                    json.dumps(request.metadata),
                    request.source.value,
                    tier.value,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
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
        """Initialize all databases in a given scope."""
        
        db_types = ["local", "global", "frozen"]
        
        for db_type in db_types:
            # Skip local/global/frozen that don't belong to this scope
            if scope == "local" and db_type in ["global", "frozen"]:
                continue
            if scope == "global" and db_type == "local":
                continue
            
            db_path = topology.resolve(scope, db_type)
            
            # Skip if not applicable
            if db_path is None:
                continue
            
            db_path = topology.resolve(scope, db_type)
            if db_path is None:
                continue

            # Authority Connection
            conn = topology.connect(scope, db_type)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.executescript(cls.SCHEMA_SQL)
                conn.commit()
                logger.debug(f"Initialized kernel schema for {scope}/{db_type}")
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
