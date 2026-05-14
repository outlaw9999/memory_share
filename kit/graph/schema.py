import logging
import sqlite3

logger = logging.getLogger("kit.graph.schema")

STRUCTURE_EDGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS structure_edges (
    source_symbol TEXT NOT NULL,
    target_symbol TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    language TEXT,
    confidence REAL DEFAULT 1.0,
    source_file TEXT,
    line INTEGER,
    PRIMARY KEY (source_symbol, target_symbol, edge_type)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS call_resolutions (
    call_site TEXT NOT NULL,
    callee_canonical TEXT NOT NULL,
    source_file TEXT,
    line INTEGER,
    confidence REAL DEFAULT 1.0,
    resolution_method TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (call_site, callee_canonical, source_file, line)
);
"""

EDGES_VIEW_QUERIES = """
CREATE VIEW IF NOT EXISTS import_graph AS
SELECT source_symbol, target_symbol, confidence
FROM structure_edges
WHERE edge_type = 'IMPORTS';

CREATE VIEW IF NOT EXISTS inheritance_graph AS
SELECT source_symbol, target_symbol, confidence
FROM structure_edges
WHERE edge_type = 'INHERITS';

CREATE VIEW IF NOT EXISTS call_graph AS
SELECT source_symbol, target_symbol, confidence
FROM structure_edges
WHERE edge_type = 'CALLS';

CREATE VIEW IF NOT EXISTS execution_graph AS
SELECT
    se.source_symbol,
    se.target_symbol,
    se.confidence,
    se.source_file,
    se.line,
    cr.resolution_method
FROM structure_edges se
LEFT JOIN call_resolutions cr ON
    se.source_symbol = cr.call_site
    AND se.target_symbol = cr.callee_canonical
WHERE se.edge_type = 'CALLS';

CREATE VIEW IF NOT EXISTS resolved_calls AS
SELECT
    cr.call_site,
    cr.callee_canonical,
    cr.confidence,
    cr.resolution_method,
    cr.source_file,
    cr.line
FROM call_resolutions cr
WHERE cr.resolution_method != 'unresolved';
"""


def init_graph_db(conn: sqlite3.Connection):
    """Initialize graph storage layer."""
    conn.executescript(STRUCTURE_EDGES_SCHEMA)
    conn.executescript(EDGES_VIEW_QUERIES)
    logger.info("Graph schema initialized: structure_edges + call_resolutions")


def get_edge_counts(conn: sqlite3.Connection) -> dict:
    """Return edge counts by type."""
    cur = conn.execute("""
        SELECT edge_type, COUNT(*) as cnt
        FROM structure_edges
        GROUP BY edge_type
    """)
    return dict(cur.fetchall())


def migrate_call_resolutions(conn: sqlite3.Connection) -> int:
    """Migrate call_resolutions table if not exists."""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS call_resolutions (
                call_site TEXT NOT NULL,
                callee_canonical TEXT NOT NULL,
                source_file TEXT,
                line INTEGER,
                confidence REAL DEFAULT 1.0,
                resolution_method TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (call_site, callee_canonical, source_file, line)
            )
        """)

        conn.execute("""
            CREATE VIEW IF NOT EXISTS execution_graph AS
            SELECT
                se.source_symbol,
                se.target_symbol,
                se.confidence,
                se.source_file,
                se.line,
                cr.resolution_method
            FROM structure_edges se
            LEFT JOIN call_resolutions cr ON
                se.source_symbol = cr.call_site
                AND se.target_symbol = cr.callee_canonical
            WHERE se.edge_type = 'CALLS'
        """)

        conn.execute("""
            CREATE VIEW IF NOT EXISTS resolved_calls AS
            SELECT
                cr.call_site,
                cr.callee_canonical,
                cr.confidence,
                cr.resolution_method,
                cr.source_file,
                cr.line
            FROM call_resolutions cr
            WHERE cr.resolution_method != 'unresolved'
        """)

        logger.info("Migrated: call_resolutions table + execution_graph views")
        return 1
    except sqlite3.OperationalError as e:
        logger.warning(f"Migration skipped: {e}")
        return 0
