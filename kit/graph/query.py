"""
KIT Graph Query Engine v1

Core traversal: blast radius, dependency chain, influence.
"""

import logging
import sqlite3
from enum import Enum
from typing import Optional

logger = logging.getLogger("kit.graph.query")


class TraversalDirection(Enum):
    FORWARD = "forward"
    BACKWARD = "backward"
    BIDIRECTIONAL = "bidirectional"


def get_blast_radius(
    conn: sqlite3.Connection,
    start_symbol: str,
    max_depth: int = 5,
    direction: TraversalDirection = TraversalDirection.BIDIRECTIONAL,
    edge_types: tuple | None = None,
    include_confidence: bool = False,
) -> list:
    """Recursive CTE blast radius traversal."""
    if edge_types is None:
        edge_types = ("IMPORTS", "INHERITS", "CALLS")

    placeholders = ",".join("?" * len(edge_types))
    edge_list = list(edge_types)

    if direction == TraversalDirection.FORWARD:
        cte_sql = f"""
        WITH RECURSIVE blast_radius(symbol, distance, edge_type, path) AS (
            SELECT target_symbol, 0, edge_type, source_symbol || ' -> ' || target_symbol
            FROM structure_edges
            WHERE source_symbol = ? AND edge_type IN ({placeholders})
            UNION ALL
            SELECT se.target_symbol, br.distance + 1, se.edge_type, br.path || ' -> ' || se.target_symbol
            FROM structure_edges se
            JOIN blast_radius br ON se.source_symbol = br.symbol
            WHERE br.distance < ? AND se.edge_type IN ({placeholders})
        )
        """
        params = [start_symbol] + edge_list + [max_depth - 1] + edge_list

    elif direction == TraversalDirection.BACKWARD:
        cte_sql = f"""
        WITH RECURSIVE blast_radius(symbol, distance, edge_type, path) AS (
            SELECT source_symbol, 0, edge_type, target_symbol || ' <- ' || source_symbol
            FROM structure_edges
            WHERE target_symbol = ? AND edge_type IN ({placeholders})
            UNION ALL
            SELECT se.source_symbol, br.distance + 1, se.edge_type, br.path || ' <- ' || se.target_symbol
            FROM structure_edges se
            JOIN blast_radius br ON se.target_symbol = br.symbol
            WHERE br.distance < ? AND se.edge_type IN ({placeholders})
        )
        """
        params = [start_symbol] + edge_list + [max_depth - 1] + edge_list

    else:
        cte_sql = f"""
        WITH RECURSIVE forward(symbol, distance, edge_type, path) AS (
            SELECT target_symbol, 0, edge_type, source_symbol || ' -> ' || target_symbol
            FROM structure_edges
            WHERE source_symbol = ? AND edge_type IN ({placeholders})
            UNION ALL
            SELECT se.target_symbol, fwd.distance + 1, se.edge_type, fwd.path || ' -> ' || se.target_symbol
            FROM structure_edges se
            JOIN forward fwd ON se.source_symbol = fwd.symbol
            WHERE fwd.distance < ? AND se.edge_type IN ({placeholders})
        ),
        backward(symbol, distance, edge_type, path) AS (
            SELECT source_symbol, 0, edge_type, target_symbol || ' <- ' || source_symbol
            FROM structure_edges
            WHERE target_symbol = ? AND edge_type IN ({placeholders})
            UNION ALL
            SELECT se.source_symbol, bwd.distance + 1, se.edge_type, bwd.path || ' <- ' || se.target_symbol
            FROM structure_edges se
            JOIN backward bwd ON se.target_symbol = bwd.symbol
            WHERE bwd.distance < ? AND se.edge_type IN ({placeholders})
        ),
        blast_radius(symbol, distance, edge_type, path) AS (
            SELECT symbol, distance, edge_type, path FROM forward
            UNION
            SELECT symbol, distance, edge_type, path FROM backward
        )
        """
        params = (
            [start_symbol]
            + edge_list
            + [max_depth - 1]
            + edge_list
            + [start_symbol]
            + edge_list
            + [max_depth - 1]
            + edge_list
        )

    if include_confidence:
        select_sql = "SELECT DISTINCT symbol, distance, edge_type, confidence FROM blast_radius ORDER BY distance"
        result = conn.execute(cte_sql + select_sql, params).fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in result]
    else:
        select_sql = "SELECT DISTINCT symbol, distance, edge_type FROM blast_radius ORDER BY distance"
        result = conn.execute(cte_sql + select_sql, params).fetchall()
        return [(r[0], r[1], r[2]) for r in result]


def find_connected_components(conn: sqlite3.Connection, symbols: list) -> dict:
    """Find connected component for given symbols."""
    if not symbols:
        return []

    ",".join("?" * len(symbols))

    result = conn.execute(
        """
        WITH RECURSIVE cc(symbol, root) AS (
            SELECT ?, ?
            UNION
            SELECT se.target_symbol, cc.root
            FROM structure_edges se
            JOIN cc ON se.source_symbol = cc.symbol
            WHERE se.edge_type IN ('IMPORTS', 'INHERITS')
        )
        SELECT DISTINCT symbol FROM cc
    """,
        (symbols[0], symbols[0]),
    ).fetchall()

    return [r[0] for r in result]


def get_import_chain(conn: sqlite3.Connection, from_sym: str, to_sym: str) -> list:
    """Find shortest path from one symbol to another."""
    result = conn.execute(
        """
        WITH RECURSIVE path_finder(source, target, distance, path) AS (
            SELECT source_symbol, target_symbol, 0, source_symbol || ' -> ' || target_symbol
            FROM structure_edges
            WHERE source_symbol = ? AND edge_type = 'IMPORTS'
            UNION ALL
            SELECT se.source_symbol, se.target_symbol, pf.distance + 1, pf.path || ' -> ' || se.target_symbol
            FROM structure_edges se
            JOIN path_finder pf ON se.source_symbol = pf.target
            WHERE pf.distance < 10 AND edge_type = 'IMPORTS'
        )
        SELECT path FROM path_finder WHERE target = ? LIMIT 1
    """,
        (from_sym, to_sym),
    ).fetchone()

    return [result[0]] if result else []
