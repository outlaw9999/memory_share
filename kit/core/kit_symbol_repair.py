"""Titanium Symbol Repair Engine (v1.2.5-STAGE5.3).

Heuristic-based auto-repair for symbol debt with governance guards:
- Confidence threshold per domain (domain-aware repair)
- Multi-match scoring (best match wins, not first match)
- Hierarchical protection (only migrate flat symbols)
- Symbol depth validation
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kit.core.kit_cognitive_core import SAMBrain

logger = logging.getLogger("kit.symbol_repair")

SYMBOL_HEURISTICS = {
    "db.sql.query": (r"db|sql|connection|pool|query|sqlite|migration", 0.85),
    "auth.secure.token": (r"auth|login|token|password|session|permission|secure", 0.85),
    "arch.vcs.git": (r"git|commit|branch|push|pull|merge|vcs|repo", 0.90),
    "arch.kernel.cognitive": (r"kit|kernel|brain|recall|learn|cognitive|epistemic|reflection", 0.80),
    "arch.env.topology": (r"venv|python|path|env|substrate|cwd|topology", 0.80),
    "arch.infra.hygiene": (r"snapshot|restore|retention|hygiene|doctor|wal|shm|telemetry", 0.80),
    "arch.design.pattern": (r"pattern|invariant|decision|layer|topology|boundary|contract", 0.75),
    "agent.core.reasoning": (r"agent|antigravity|prompt|context|thinking|reasoning", 0.75),
    "fin.market.stock": (r"stock|vnstock|ptck|ticker|price|ohlc|finance", 0.85),
    "test.synthetic.data": (r"fact \d+|parallel|test|cycle \d+", 0.70),
}

CONFIDENCE_THRESHOLD = 0.75

MIN_CONFIDENCE_BY_DOMAIN = {
    "db": 0.70,
    "auth": 0.80,
    "arch": 0.85,
}


def get_domain(symbol: str) -> str:
    """Extract domain from symbol (e.g., 'db' from 'db.sql.query')."""
    return symbol.split(".")[0] if "." in symbol else ""


def get_min_confidence(symbol: str) -> float:
    """Get domain-aware minimum confidence threshold."""
    domain = get_domain(symbol)
    return MIN_CONFIDENCE_BY_DOMAIN.get(domain, CONFIDENCE_THRESHOLD)


def validate_symbol_depth(symbol: str, max_depth: int = 4) -> bool:
    """Ensure symbol taxonomy doesn't become over-disciplined."""
    if not symbol:
        return True
    return len(symbol.split(".")) <= max_depth


def repair_symbol_debt(brain: SAMBrain) -> int:
    """Analyze memories with null symbols and assign symbols based on heuristics."""
    repaired_count = 0
    
    # 1. Repair Local
    with brain.get_connection() as conn:
        repaired_count += _repair_db(conn, "local")
    
    # 2. Repair Global (if attached)
    if hasattr(brain, "global_db_path") and brain.global_db_path:
        try:
            # We need a dedicated connection for global write if possible
            # But normally we connect to global in SAMBrain.
            from kit.core.memory_topology import MemoryTopology
            topo = MemoryTopology(brain.root_path)
            conn_global = topo.connect("global", "global", readonly=False)
            repaired_count += _repair_db(conn_global, "global")
            conn_global.close()
        except Exception as e:
            logger.warning(f"Symbol Repair: Failed to repair global DB: {e}")
            
    return repaired_count


def _repair_db(conn: sqlite3.Connection, label: str) -> int:
    """Internal helper to repair/migrate symbols for a specific database."""
    repaired = 0
    migrated = 0
    skipped_protected = 0
    skipped_locked = 0
    try:
        rows = conn.execute("""
            SELECT id, content, symbol, COALESCE(symbol_locked, 0) 
            FROM observations 
            WHERE is_active = 1
        """).fetchall()

        for row in rows:
            obs_id, content, current_symbol, symbol_locked = row
            content_lower = content.lower()

            matches = []
            for target_symbol, (pattern, confidence) in SYMBOL_HEURISTICS.items():
                min_conf = get_min_confidence(target_symbol)
                if confidence < min_conf:
                    continue
                if re.search(pattern, content_lower):
                    matches.append((target_symbol, confidence))

            if not matches:
                if symbol_locked == 1:
                    skipped_locked += 1
                continue

            target_symbol, confidence = max(matches, key=lambda x: x[1])
            
            # v1.2.5-STAGE5.5: Record ambiguity sensor even if locked
            if len(matches) > 1 or (current_symbol and current_symbol != target_symbol):
                import json
                candidates_json = json.dumps([(m[0], m[1]) for m in matches])
                try:
                    conn.execute(
                        "INSERT INTO symbol_ambiguities (observation_id, chosen_symbol, candidates, confidence) VALUES (?, ?, ?, ?)",
                        (obs_id, target_symbol, candidates_json, confidence)
                    )
                except sqlite3.OperationalError:
                    pass

            if symbol_locked == 1:
                skipped_locked += 1
                continue
            if len(matches) > 1:
                import json
                candidates_json = json.dumps([(m[0], m[1]) for m in matches])
                logger.info(
                    f"Symbol ambiguity resolved for obs {obs_id}: {len(matches)} candidates → {target_symbol} "
                    f"(conf={confidence:.2f}, candidates={candidates_json})"
                )
                try:
                    conn.execute(
                        "INSERT INTO symbol_ambiguities (observation_id, chosen_symbol, candidates, confidence) VALUES (?, ?, ?, ?)",
                        (obs_id, target_symbol, candidates_json, confidence)
                    )
                except sqlite3.OperationalError:
                    pass

            is_flat = not current_symbol or ("." not in current_symbol)

            if not current_symbol:
                if validate_symbol_depth(target_symbol):
                    conn.execute(
                        "UPDATE observations SET symbol = ?, symbol_confidence = ?, symbol_source = ? WHERE id = ?",
                        (target_symbol, confidence, "heuristic", obs_id)
                    )
                    repaired += 1
            elif is_flat and current_symbol != target_symbol:
                if validate_symbol_depth(target_symbol):
                    conn.execute(
                        "UPDATE observations SET symbol = ?, symbol_confidence = ?, symbol_source = ? WHERE id = ?",
                        (target_symbol, confidence, "heuristic", obs_id)
                    )
                    migrated += 1
            else:
                skipped_protected += 1

        if repaired > 0 or migrated > 0:
            conn.commit()
            logger.info(f"Symbol Governance [{label}]: {repaired} repaired, {migrated} migrated, {skipped_protected} protected, {skipped_locked} locked.")
    except Exception as e:
        logger.error(f"Symbol Governance [{label}]: Error: {e}")

    return repaired + migrated
        
    return repaired + migrated
