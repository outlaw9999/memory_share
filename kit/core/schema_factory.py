import logging
import sqlite3

logger = logging.getLogger("kit.schema")


def quote_identifier(identifier: str) -> str:
    """Quote a SQLite identifier defensively."""
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kernel_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Initialize Kernel Identity (v1.2.5)
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('version', '1.2.5');
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('kit_schema_version', '1.2.5');
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('vantage_contract_version', '1.2.5-rust');
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('integrity_policy', 'strict');
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('write_authority', 'MemoryRouter');

CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,
    kind TEXT,
    node_type TEXT CHECK(node_type IN ('skill', 'law', 'config', 'artifact', 'entity', 'observation')) DEFAULT 'observation',
    status TEXT CHECK(status IN ('active', 'frozen', 'archived')) DEFAULT 'active',
    visibility TEXT CHECK(visibility IN ('local', 'global')) DEFAULT 'local',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    predicate TEXT NOT NULL,
    object_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    superseded_at DATETIME,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (subject_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (object_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS commits (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    agent_id TEXT,
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS branches (
    name TEXT PRIMARY KEY,
    head_commit_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    agent_id TEXT,
    version INTEGER DEFAULT 0,
    FOREIGN KEY (head_commit_id) REFERENCES commits(id)
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    layer TEXT CHECK(layer IN ('working', 'episodic', 'semantic', 'procedural')) DEFAULT 'episodic',
    tag TEXT CHECK(tag IN ('invariant', 'decision', 'preference', 'note', 'legacy', 'friction', 'skill', 'pattern', 'hypothesis')) DEFAULT 'decision',
    importance REAL DEFAULT 1.0,
    materialized_score REAL NOT NULL DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at_bucket INTEGER GENERATED ALWAYS AS (CAST(strftime('%Y%m%d%H', created_at) AS INTEGER)) VIRTUAL,
    superseded_at DATETIME,
    last_accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    namespace TEXT DEFAULT 'shared',
    scope TEXT NOT NULL DEFAULT '',
    branch TEXT DEFAULT 'main',
    symbol TEXT,
    symbol_locked INTEGER DEFAULT 0,
    symbol_confidence REAL DEFAULT 0.0,
    symbol_source TEXT,
    structural_hash TEXT,
    agent_id TEXT,
    metadata TEXT DEFAULT '{}',
    commit_id TEXT,
    is_active BOOLEAN DEFAULT 1,
    is_baked BOOLEAN DEFAULT 0,
    is_canonical INTEGER DEFAULT 0,
    canonical_id INTEGER,
    supersedes_id INTEGER DEFAULT NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (commit_id) REFERENCES commits(id),
    FOREIGN KEY (supersedes_id) REFERENCES observations(id) ON DELETE SET NULL,
    FOREIGN KEY (canonical_id) REFERENCES observations(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    signal TEXT,
    scope TEXT,
    outcome TEXT,
    latency_ms REAL,
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metrics_event ON metrics(event_type);
CREATE INDEX IF NOT EXISTS idx_metrics_created ON metrics(created_at);

-- --- Flow System v0.1.2
CREATE TABLE IF NOT EXISTS flow_runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT,
    state TEXT CHECK(state IN ('planned', 'running', 'committing', 'success', 'failed', 'rolled_back')) DEFAULT 'planned',
    mode TEXT DEFAULT 'strict',
    metadata TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flow_steps (
    id TEXT PRIMARY KEY,
    flow_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    command TEXT NOT NULL,
    state TEXT CHECK(state IN ('pending', 'running', 'success', 'failed', 'rolled_back')) DEFAULT 'pending',
    depends_on TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    idempotent BOOLEAN DEFAULT 1,
    frame_id TEXT,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (flow_id) REFERENCES flow_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS flow_transactions (
    id TEXT PRIMARY KEY,
    flow_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    state TEXT CHECK(state IN ('open', 'committed', 'rolled_back', 'failed')) DEFAULT 'open',
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (flow_id) REFERENCES flow_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS flow_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    state_snapshot TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (flow_id) REFERENCES flow_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    parent_hash TEXT,
    snapshot_hash TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    path TEXT,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (parent_id) REFERENCES snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);

CREATE TABLE IF NOT EXISTS symbol_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_symbol TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    target_symbol TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_symbol_edges_src ON symbol_edges(source_symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_edges_target ON symbol_edges(target_symbol);

CREATE TABLE IF NOT EXISTS symbol_ambiguities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL,
    chosen_symbol TEXT NOT NULL,
    candidates TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_symbol_ambiguities_obs ON symbol_ambiguities(observation_id);

-- --- Stage 5.5: SRE
CREATE TABLE IF NOT EXISTS symbol_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    locked INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS symbol_evolution_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_symbol_id INTEGER NOT NULL,
    to_symbol_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    rationale_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_symbol_id) REFERENCES symbol_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (to_symbol_id) REFERENCES symbol_nodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS symbol_drift_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    metrics_json TEXT DEFAULT '{}',
    final_score REAL DEFAULT 0.0,
    status TEXT DEFAULT 'STABLE',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS symbol_reconciliation_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    proposed_symbol TEXT NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_symbol_drift_symbol ON symbol_drift_events(symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_nodes_symbol ON symbol_nodes(symbol);
"""

# Views created AFTER all migrations complete (they reference is_active, is_baked, etc.)
VIEWS_SQL = """
CREATE VIEW IF NOT EXISTS baked_observations AS
SELECT
    id, node_id, content, tag, importance, created_at, structural_hash
FROM observations
WHERE is_active = 1 AND is_baked = 1 AND superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_obs_vantage_read ON observations(is_active, is_baked, superseded_at);
"""


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols


def _add_column_safe(conn: sqlite3.Connection, table: str, column: str, definition: str, backfill: str | None = None):
    """Add column if it doesn't exist, optionally backfill."""
    if not _column_exists(conn, table, column):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
            logger.info(f"Migrated: Added {column} to {table}")
        except sqlite3.OperationalError:
            return  # Another process may have added it
    # Always backfill if requested
    if backfill:
        try:
            conn.execute(backfill)
            logger.info(f"Backfilled: {column} in {table}")
        except sqlite3.OperationalError:
            pass


def _ensure_index(conn: sqlite3.Connection, name: str, ddl: str):
    """Create index if not exists, ignoring errors."""
    try:
        conn.execute(ddl)
    except sqlite3.OperationalError:
        pass


def init_db(conn: sqlite3.Connection):
    """Bootstrap or migrate the database schema (v1.2.5)."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    # === Phase 1: Create core tables ===
    conn.executescript(SCHEMA_SQL)

    # === Phase 2: Migrations (old DB → v1.2.5) ===

    # Chronos patch: superseded_at
    _add_column_safe(conn, "observations", "superseded_at", "superseded_at DATETIME")

    # Namespace
    _add_column_safe(conn, "observations", "namespace", "namespace TEXT DEFAULT 'shared'")

    # Commit tracking
    _add_column_safe(conn, "observations", "commit_id", "commit_id TEXT")

    # Branch
    _add_column_safe(conn, "observations", "branch", "branch TEXT DEFAULT 'main'")

    # Scope
    _add_column_safe(conn, "observations", "scope", "scope TEXT NOT NULL DEFAULT ''")

    # Initialize ROOT commit and main branch
    try:
        conn.execute(
            "INSERT OR IGNORE INTO commits (id, agent_id, message) VALUES ('ROOT', 'system', 'Initial cognitive root')"
        )
        conn.execute("INSERT OR IGNORE INTO branches (name, head_commit_id) VALUES ('main', 'ROOT')")
    except sqlite3.OperationalError:
        pass

    # Branch version
    _add_column_safe(conn, "branches", "version", "version INTEGER DEFAULT 0")

    # Symbol tracking
    _add_column_safe(conn, "observations", "symbol", "symbol TEXT")
    _add_column_safe(conn, "observations", "structural_hash", "structural_hash TEXT")

    # Symbol Governance (v1.2.5)
    _add_column_safe(conn, "observations", "symbol_locked", "symbol_locked INTEGER DEFAULT 0")
    _add_column_safe(conn, "observations", "symbol_confidence", "symbol_confidence REAL DEFAULT 0.0")
    _add_column_safe(conn, "observations", "symbol_source", "symbol_source TEXT")

    # Canonical Model
    _add_column_safe(conn, "observations", "is_canonical", "is_canonical INTEGER DEFAULT 0")
    _add_column_safe(conn, "observations", "canonical_id", "canonical_id INTEGER")

    # Perception-Cognition split (1.2.5LOCK)
    _add_column_safe(
        conn,
        "observations",
        "is_baked",
        "is_baked BOOLEAN DEFAULT 0",
        backfill="UPDATE observations SET is_baked = 1 WHERE is_baked IS NULL OR is_baked = 0",
    )

    # Baked index
    _ensure_index(conn, "idx_obs_baked", "CREATE INDEX IF NOT EXISTS idx_obs_baked ON observations(is_baked)")

    # Supersedes
    _add_column_safe(conn, "observations", "supersedes_id", "supersedes_id INTEGER")

    # === Phase 3: Indices & triggers (post-migration) ===
    try:
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_obs_canonical ON observations(canonical_id) WHERE canonical_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_obs_is_canonical ON observations(is_canonical) WHERE is_canonical = 1;
            CREATE INDEX IF NOT EXISTS idx_obs_created ON observations(created_at);
            CREATE INDEX IF NOT EXISTS idx_obs_is_active ON observations(is_active) WHERE is_active = 1;

            CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
                content,
                content='observations',
                content_rowid='id',
                tokenize='porter'
            );

            CREATE TRIGGER IF NOT EXISTS observations_ai AFTER INSERT ON observations BEGIN
                INSERT INTO observations_fts(rowid, content) VALUES (new.id, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS observations_au AFTER UPDATE ON observations BEGIN
                INSERT INTO observations_fts(observations_fts, rowid, content) VALUES('delete', old.id, old.content);
                INSERT INTO observations_fts(rowid, content) VALUES (new.id, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS observations_ad AFTER DELETE ON observations BEGIN
                INSERT INTO observations_fts(observations_fts, rowid, content) VALUES('delete', old.id, old.content);
            END;
        """)
    except sqlite3.OperationalError:
        pass

    # Tag migration (v1.2.3): Expand allowed tags
    try:
        cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='observations'")
        row = cur.fetchone()
        if row:
            schema_sql = row[0]
            if "hypothesis" not in schema_sql or "pattern" not in schema_sql or "skill" not in schema_sql:
                logger.info("Migrating observations table to expand tag constraints (v1.2.3.3)...")
                conn.execute("PRAGMA foreign_keys=OFF")

                conn.execute("DROP TABLE IF EXISTS observations_new")
                conn.execute("""
                CREATE TABLE observations_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    layer TEXT CHECK(layer IN ('working', 'episodic', 'semantic', 'procedural')) DEFAULT 'episodic',
                    tag TEXT CHECK(tag IN ('invariant', 'decision', 'preference', 'note', 'legacy', 'friction', 'skill', 'pattern', 'hypothesis')) DEFAULT 'decision',
                    importance REAL DEFAULT 1.0,
                    materialized_score REAL NOT NULL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    superseded_at DATETIME,
                    last_accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    namespace TEXT DEFAULT 'shared',
                    scope TEXT NOT NULL DEFAULT '',
                    branch TEXT DEFAULT 'main',
                    symbol TEXT,
                    symbol_locked INTEGER DEFAULT 0,
                    symbol_confidence REAL DEFAULT 0.0,
                    symbol_source TEXT,
                    structural_hash TEXT,
                    metadata TEXT DEFAULT '{}',
                    commit_id TEXT,
                    agent_id TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    is_baked BOOLEAN DEFAULT 0,
                    is_canonical INTEGER DEFAULT 0,
                    canonical_id INTEGER,
                    supersedes_id INTEGER,
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (commit_id) REFERENCES commits(id),
                    FOREIGN KEY (supersedes_id) REFERENCES observations(id) ON DELETE SET NULL,
                    FOREIGN KEY (canonical_id) REFERENCES observations(id) ON DELETE SET NULL
                )
                """)

                cols_cur = conn.execute("PRAGMA table_info(observations)")
                cols = [col[1] for col in cols_cur.fetchall()]
                cols_str = ", ".join(quote_identifier(col) for col in cols)
                conn.execute(f"INSERT INTO observations_new ({cols_str}) SELECT {cols_str} FROM observations")

                conn.execute("DROP TABLE observations")
                conn.execute("ALTER TABLE observations_new RENAME TO observations")

                conn.execute("PRAGMA foreign_keys=ON")
                logger.info("Successfully migrated observations table constraints.")
    except Exception as e:
        logger.warning(f"Migration failed or skipped: {e}")
        conn.execute("PRAGMA foreign_keys=ON")

    # materialized_score
    _add_column_safe(conn, "observations", "materialized_score", "materialized_score REAL NOT NULL DEFAULT 1.0")

    is_active_backfill = """
    UPDATE observations SET is_active = 1 WHERE is_active IS NULL
    """
    _add_column_safe(conn, "observations", "is_active", "is_active BOOLEAN DEFAULT 1", backfill=is_active_backfill)

    # created_at_bucket
    try:
        conn.execute(
            "ALTER TABLE observations ADD COLUMN created_at_bucket INTEGER GENERATED ALWAYS AS (CAST(strftime('%Y%m%d%H', created_at) AS INTEGER)) VIRTUAL"
        )
        logger.info("Migrated: Added created_at_bucket to observations")
    except sqlite3.OperationalError:
        pass

    # === Phase 4: Final indexes ===
    _ensure_index(
        conn,
        "idx_obs_bucket",
        "CREATE INDEX IF NOT EXISTS idx_obs_bucket ON observations(created_at_bucket, importance)",
    )
    _ensure_index(conn, "idx_nodes_uid", "CREATE INDEX IF NOT EXISTS idx_nodes_uid ON nodes(uid)")
    _ensure_index(conn, "idx_obs_node", "CREATE INDEX IF NOT EXISTS idx_obs_node ON observations(node_id)")
    _ensure_index(conn, "idx_obs_commit", "CREATE INDEX IF NOT EXISTS idx_obs_commit ON observations(commit_id)")
    _ensure_index(conn, "idx_obs_branch", "CREATE INDEX IF NOT EXISTS idx_obs_branch ON observations(branch)")
    _ensure_index(conn, "idx_obs_namespace", "CREATE INDEX IF NOT EXISTS idx_obs_namespace ON observations(namespace)")
    _ensure_index(
        conn,
        "idx_obs_scope_created",
        "CREATE INDEX IF NOT EXISTS idx_obs_scope_created ON observations(scope, created_at DESC)",
    )
    _ensure_index(
        conn, "idx_obs_node_scope", "CREATE INDEX IF NOT EXISTS idx_obs_node_scope ON observations(node_id, scope)"
    )
    _ensure_index(conn, "idx_obs_symbol", "CREATE INDEX IF NOT EXISTS idx_obs_symbol ON observations(symbol)")
    _ensure_index(
        conn,
        "idx_obs_active_score",
        "CREATE INDEX IF NOT EXISTS idx_obs_active_score ON observations(is_active, materialized_score DESC)",
    )
    _ensure_index(conn, "idx_obs_hash", "CREATE INDEX IF NOT EXISTS idx_obs_hash ON observations(structural_hash)")
    _ensure_index(
        conn,
        "idx_obs_recall_optimized",
        "CREATE INDEX IF NOT EXISTS idx_obs_recall_optimized ON observations(is_active, scope, materialized_score DESC)",
    )
    _ensure_index(conn, "idx_metrics_event", "CREATE INDEX IF NOT EXISTS idx_metrics_event ON metrics(event_type)")

    # === Phase 5: Symbol Reconciliation Engine ===
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS symbol_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            locked INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS symbol_evolution_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_symbol_id INTEGER NOT NULL,
            to_symbol_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            rationale_json TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_symbol_id) REFERENCES symbol_nodes(id) ON DELETE CASCADE,
            FOREIGN KEY (to_symbol_id) REFERENCES symbol_nodes(id) ON DELETE CASCADE
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS symbol_drift_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            metrics_json TEXT DEFAULT '{}',
            final_score REAL DEFAULT 0.0,
            status TEXT DEFAULT 'STABLE',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS symbol_reconciliation_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            proposed_symbol TEXT NOT NULL,
            confidence REAL NOT NULL,
            rationale TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_drift_symbol ON symbol_drift_events(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_nodes_symbol ON symbol_nodes(symbol)")
        logger.info("Migrated: Created Stage 5.5 SRE tables")
    except sqlite3.OperationalError as e:
        logger.warning(f"Migration: Failed to create SRE tables: {e}")

    # Snapshot integrity chain
    try:
        conn.execute("ALTER TABLE snapshots ADD COLUMN parent_hash TEXT")
        conn.execute("ALTER TABLE snapshots ADD COLUMN snapshot_hash TEXT")
        logger.info("Migrated: Added parent_hash and snapshot_hash to snapshots")
    except sqlite3.OperationalError:
        pass

    # Backfill symbol_nodes
    try:
        conn.execute("""
            INSERT OR IGNORE INTO symbol_nodes (symbol, locked)
            SELECT DISTINCT symbol, 1 FROM observations WHERE symbol_locked = 1 AND symbol IS NOT NULL
        """)
        conn.execute("""
            INSERT OR IGNORE INTO symbol_nodes (symbol, locked)
            SELECT DISTINCT symbol, 0 FROM observations WHERE (symbol_locked = 0 OR symbol_locked IS NULL) AND symbol IS NOT NULL
        """)
    except sqlite3.OperationalError:
        pass

    # === Phase 6: Create views (AFTER all migrations!) ===
    try:
        conn.executescript(VIEWS_SQL)
        logger.info("Views created: baked_observations")
    except sqlite3.OperationalError:
        pass


def enable_wal(conn: sqlite3.Connection):
    """Activate high-performance mode (v1.2.5 Tuning)."""
    mode_row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    if mode_row:
        mode = mode_row[0] if isinstance(mode_row, tuple) else mode_row["journal_mode"]
        if mode.lower() != "wal":
            logger.warning(f"Failed to enable WAL mode. Current mode: {mode}")

    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA read_uncommitted=1")
