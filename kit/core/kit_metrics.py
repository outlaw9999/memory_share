"""Titanium Metrics Engine (v1.2.4-STAGE5).

Calculates Global Quality Index (GQI) and Entropy for cognitive health.
"""

from __future__ import annotations
import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("kit.metrics")

@dataclass(frozen=True, slots=True)
class GlobalQualityIndex:
    total_memories: int
    symbol_null_count: int
    symbol_debt_ratio: float
    symbol_structured_count: int
    symbol_structured_ratio: float
    duplicate_count: int
    duplicate_ratio: float
    orphan_edge_count: int
    orphan_ratio: float
    entropy_score: float
    quality_score: float
    recall_hit_rate: float
    avg_recall_latency_ms: float
    timestamp: str

def calculate_gqi(conn: sqlite3.Connection) -> GlobalQualityIndex:
    """Compute the holistic health of the memory kernel."""
    import re
    
    # 1. Total active memories
    total = conn.execute("SELECT COUNT(*) FROM observations WHERE is_active = 1").fetchone()[0]
    if total == 0:
        return GlobalQualityIndex(0, 0, 0.0, 0, 0.0, 0, 0.0, 0, 0.0, 0.0, 0.0, datetime.now().isoformat())

    # 2. Symbol Debt (NULL or Empty)
    null_symbols = conn.execute(
        "SELECT COUNT(*) FROM observations WHERE (symbol IS NULL OR symbol = '') AND is_active = 1"
    ).fetchone()[0]
    symbol_debt_ratio = null_symbols / total

    # 2b. Symbol Structure (Hierarchical Governance: domain.subdomain.target)
    # A structured symbol must contain at least one dot and not be a UUID
    structured_rows = conn.execute("""
        SELECT symbol FROM observations 
        WHERE symbol IS NOT NULL AND symbol != '' AND is_active = 1
    """).fetchall()
    
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    structured_count = 0
    for (sym,) in structured_rows:
        if "." in sym and not re.match(uuid_pattern, sym):
            structured_count += 1
            
    symbol_structured_ratio = structured_count / (total - null_symbols) if (total - null_symbols) > 0 else 0.0

    # 3. Duplicate Rate
    # Count how many memories have content that appears more than once
    duplicates = conn.execute("""
        SELECT COUNT(*) 
        FROM (
            SELECT content FROM observations 
            WHERE is_active = 1 
            GROUP BY content 
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    duplicate_ratio = duplicates / total

    # 4. Orphan Edges (Structural Entropy)
    # Edges pointing to non-existent nodes
    orphans = conn.execute("""
        SELECT COUNT(*) FROM edges 
        WHERE subject_id NOT IN (SELECT id FROM nodes)
           OR object_id NOT IN (SELECT id FROM nodes)
    """).fetchone()[0]
    total_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    orphan_ratio = orphans / total_edges if total_edges > 0 else 0.0

    # 5. Performance Pulse (Last 100 recalls)
    pulse = conn.execute("""
        SELECT 
            AVG(CASE WHEN outcome = 'hit' THEN 1.0 ELSE 0.0 END),
            AVG(latency_ms)
        FROM (
            SELECT outcome, latency_ms FROM metrics 
            WHERE event_type = 'recall_pulse' 
            ORDER BY created_at DESC LIMIT 100
        )
    """).fetchone()
    
    recall_hit_rate = pulse[0] if pulse and pulse[0] is not None else 0.0
    avg_latency = pulse[1] if pulse and pulse[1] is not None else 0.0

    # 6. Formalized Entropy (Lower is better)
    entropy_score = duplicate_ratio + symbol_debt_ratio + orphan_ratio

    # 7. Quality Score (Higher is better)
    # symbol_integrity: (1 - debt_ratio)
    symbol_integrity = 1.0 - symbol_debt_ratio
    
    # Namespace Balance
    ns_stats = get_namespace_stats(conn)
    if ns_stats:
        max_ns = max(ns_stats.values())
        ns_balance = 1.0 - (max_ns / total)
    else:
        ns_balance = 0.0
        
    quality_score = (symbol_integrity * 0.5) + (symbol_structured_ratio * 0.1) + (recall_hit_rate * 0.3) + (ns_balance * 0.1)

    return GlobalQualityIndex(
        total_memories=total,
        symbol_null_count=null_symbols,
        symbol_debt_ratio=symbol_debt_ratio,
        symbol_structured_count=structured_count,
        symbol_structured_ratio=symbol_structured_ratio,
        duplicate_count=duplicates,
        duplicate_ratio=duplicate_ratio,
        orphan_edge_count=orphans,
        orphan_ratio=orphan_ratio,
        entropy_score=entropy_score,
        quality_score=quality_score,
        recall_hit_rate=recall_hit_rate,
        avg_recall_latency_ms=avg_latency,
        timestamp=datetime.now().isoformat()
    )

def get_namespace_stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Calculate distribution of memories across namespaces."""
    rows = conn.execute("""
        SELECT namespace, COUNT(*) 
        FROM observations 
        WHERE is_active = 1 
        GROUP BY namespace 
        ORDER BY COUNT(*) DESC
    """).fetchall()
    return {row[0]: row[1] for row in rows}
