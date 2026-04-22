"""Titanium Memory Compaction Engine (v1.2.4-STAGE5.3).

Implements the Canonical Memory Model.
Instead of deleting data, it merges semantically similar memories 
under a single "Canonical" entry, preserving original records as sources.
"""

from __future__ import annotations
import logging
import sqlite3
import difflib
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kit.core.kit_cognitive_core import SAMBrain

logger = logging.getLogger("kit.compaction")

SIMILARITY_THRESHOLD = 0.70

def execute_compaction(brain: SAMBrain, namespace: str = "shared") -> dict[str, int]:
    """Perform semantic compaction on a specific namespace."""
    report = {"scanned": 0, "merged": 0, "canonicalized": 0}
    
    with brain.get_connection(readonly=False) as conn:
        # 1. Group active observations by symbol
        symbols = conn.execute("""
            SELECT DISTINCT symbol FROM observations 
            WHERE namespace = ? AND is_active = 1 AND (symbol IS NOT NULL AND symbol != '')
        """, (namespace,)).fetchall()
        
        for (symbol,) in symbols:
            report.update(_compact_symbol_group(conn, symbol, namespace))
            
    return report

def _compact_symbol_group(conn: sqlite3.Connection, symbol: str, namespace: str) -> dict[str, int]:
    """Internal helper to compact memories sharing a symbol."""
    stats = {"scanned": 0, "merged": 0, "canonicalized": 0}
    
    # Get all active observations for this symbol
    rows = conn.execute("""
        SELECT id, content, importance, created_at FROM observations 
        WHERE symbol = ? AND namespace = ? AND is_active = 1 AND is_canonical = 0
        ORDER BY created_at DESC
    """, (symbol, namespace)).fetchall()
    
    if len(rows) < 2:
        return stats

    stats["scanned"] += len(rows)
    processed_ids = set()

    for i, base_row in enumerate(rows):
        base_id, base_content, base_importance, _ = base_row
        if base_id in processed_ids:
            continue
            
        cluster = [base_id]
        
        # Look for similar memories in the remaining list
        for j in range(i + 1, len(rows)):
            target_id, target_content, _, _ = rows[j]
            if target_id in processed_ids:
                continue
            
            # Compute semantic similarity (fuzzy ratio)
            ratio = difflib.SequenceMatcher(None, base_content, target_content).ratio()
            if ratio >= SIMILARITY_THRESHOLD:
                cluster.append(target_id)
        
        if len(cluster) > 1:
            # We have a cluster! 
            # The newest one (base_id because of ORDER BY DESC) becomes Canonical
            canonical_id = base_id
            
            # Mark the canonical record
            conn.execute("""
                UPDATE observations 
                SET is_canonical = 1, importance = importance + ?
                WHERE id = ?
            """, (0.1 * (len(cluster) - 1), canonical_id))
            stats["canonicalized"] += 1
            
            # Merge others into it
            for cid in cluster:
                if cid == canonical_id:
                    continue
                
                conn.execute("""
                    UPDATE observations 
                    SET is_active = 0, 
                        canonical_id = ?, 
                        superseded_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (canonical_id, cid))
                
                # Link them in the symbol graph as 'evidence_for'
                conn.execute("""
                    INSERT INTO symbol_edges (source_symbol, relation_type, target_symbol, confidence)
                    VALUES (?, ?, ?, ?)
                """, (f"obs_{cid}", "canonical_evidence", f"obs_{canonical_id}", 1.0))
                
                processed_ids.add(cid)
                stats["merged"] += 1
                
            processed_ids.add(canonical_id)
            
    conn.commit()
    return stats
