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

-- Initialize Kernel Identity (v1.2.4-RC1-HARDENED)
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('version', '1.2.4-final');
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('kit_schema_version', '1.2.4-final');
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('vantage_contract_version', '1.2.4-rust');
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('integrity_policy', 'strict');
INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('write_authority', 'MemoryRouter');

CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,
    kind TEXT, -- Legacy: use node_type
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

-- --- Flow System v0.1.2 (Titanium Workflow Runtime Kernel) ---

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
    id TEXT PRIMARY KEY, -- flow_id + step_id
    flow_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    command TEXT NOT NULL,
    state TEXT CHECK(state IN ('pending', 'running', 'success', 'failed', 'rolled_back')) DEFAULT 'pending',
    depends_on TEXT, -- JSON list of step_ids
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    idempotent BOOLEAN DEFAULT 1,
    frame_id TEXT, -- Link to ExecutionFrame id
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (flow_id) REFERENCES flow_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS flow_transactions (
    id TEXT PRIMARY KEY, -- transaction_id
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
    state_snapshot TEXT, -- JSON blob of relevant state
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (flow_id) REFERENCES flow_runs(id) ON DELETE CASCADE
);

-- --- Vantage Verifier View v1.2.4 ---
CREATE VIEW IF NOT EXISTS baked_observations AS
SELECT
    id,
    node_id,
    content,
    tag,
    importance,
    created_at,
    structural_hash
FROM observations
WHERE is_active = 1
  AND is_baked = 1
  AND superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_obs_vantage_read ON observations(is_active, is_baked, superseded_at);

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

-- --- Stage 5.5: Symbol Reconciliation Engine (SRE) ---

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
    relation_type TEXT NOT NULL, -- supersedes, refines, conflicts
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
    status TEXT DEFAULT 'STABLE', -- STABLE, OBSOLETE_CANDIDATE, TRANSITION_REQUIRED
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS symbol_reconciliation_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    proposed_symbol TEXT NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending', -- pending, approved, rejected
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_symbol_drift_symbol ON symbol_drift_events(symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_nodes_symbol ON symbol_nodes(symbol);
"""


def init_db(conn: sqlite3.Connection):
    """Bootstrap or migrate the database schema."""
    # v1.2.5: Enforce concurrency-safe defaults at the source
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA_SQL)

    # Migration: Ensure superseded_at exists in observations (Chronos Patch)
    try:
        conn.execute("ALTER TABLE observations ADD COLUMN superseded_at DATETIME")
        logger.info("Migrated: Added superseded_at to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN namespace TEXT DEFAULT 'shared'")
        logger.info("Migrated: Added namespace to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN commit_id TEXT")
        logger.info("Migrated: Added commit_id to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN branch TEXT DEFAULT 'main'")
        logger.info("Migrated: Added branch to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN scope TEXT NOT NULL DEFAULT ''")
        logger.info("Migrated: Added scope to observations")
    except sqlite3.OperationalError:
        pass

    # Initialize ROOT commit and main branch
    try:
        conn.execute(
            "INSERT OR IGNORE INTO commits (id, agent_id, message) VALUES ('ROOT', 'system', 'Initial cognitive root')"
        )
        conn.execute("INSERT OR IGNORE INTO branches (name, head_commit_id) VALUES ('main', 'ROOT')")
    except sqlite3.OperationalError:
        pass

    # Ensure Indexes exist (Safe after migrations)
    try:
        conn.execute("ALTER TABLE branches ADD COLUMN version INTEGER DEFAULT 0")
        logger.info("Migrated: Added version to branches")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN symbol TEXT")
        logger.info("Migrated: Added symbol to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN structural_hash TEXT")
        logger.info("Migrated: Added structural_hash to observations")
    except sqlite3.OperationalError:
        pass

    # Symbol Governance migration (v1.2.4): Add locked, confidence, source
    try:
        conn.execute("ALTER TABLE observations ADD COLUMN symbol_locked INTEGER DEFAULT 0")
        logger.info("Migrated: Added symbol_locked to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN symbol_confidence REAL DEFAULT 0.0")
        logger.info("Migrated: Added symbol_confidence to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN symbol_source TEXT")
        logger.info("Migrated: Added symbol_source to observations")
    except sqlite3.OperationalError:
        pass

    # v1.2.4-TITANIUM: Canonical Model Support
    try:
        conn.execute("ALTER TABLE observations ADD COLUMN is_canonical INTEGER DEFAULT 0")
        logger.info("Migrated: Added is_canonical to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN canonical_id INTEGER REFERENCES observations(id)")
        logger.info("Migrated: Added canonical_id to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN is_baked BOOLEAN DEFAULT 0")
        logger.info("Migrated: Added is_baked to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN supersedes_id INTEGER REFERENCES observations(id)")
        logger.info("Migrated: Added supersedes_id to observations")
    except sqlite3.OperationalError:
        pass

    # v1.2.4-TITANIUM: Re-initialize indices and triggers after columns are guaranteed
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

        -- FTS Triggers (v1.2.4-TITANIUM: Guaranteed after FTS table creation)
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

    # Symbol Ambiguities table migration
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_ambiguities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id INTEGER NOT NULL,
                chosen_symbol TEXT NOT NULL,
                candidates TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            )
        """)
        logger.info("Migrated: Created symbol_ambiguities table")
    except sqlite3.OperationalError:
        pass

    # Tag migration (v1.2.3): Expand allowed tags to include 'note' and 'legacy'
    try:
        # Check if the constraint is old
        cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='observations'")
        row = cur.fetchone()
        if row:
            schema_sql = row[0]
            if "hypothesis" not in schema_sql or "pattern" not in schema_sql or "skill" not in schema_sql:
                logger.info("Migrating observations table to expand tag constraints (v1.2.3.3)...")
                # Standard SQLite table migration pattern
                conn.execute("PRAGMA foreign_keys=OFF")

                # 1. Create new table with updated schema (using temporary name)
                # Ensure no ghost table exists from failed previous migrations
                conn.execute("DROP TABLE IF EXISTS observations_new")
                new_table_sql = """
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
                """
                conn.execute(new_table_sql)

                # 2. Copy data
                cols_cur = conn.execute("PRAGMA table_info(observations)")
                cols = [col[1] for col in cols_cur.fetchall()]
                # Filter columns that are in both old and new (to be safe)
                cols_str = ", ".join(quote_identifier(col) for col in cols)
                conn.execute(f"INSERT INTO observations_new ({cols_str}) SELECT {cols_str} FROM observations")

                # 3. Swap tables
                conn.execute("DROP TABLE observations")
                conn.execute("ALTER TABLE observations_new RENAME TO observations")

                # 4. Re-create Triggers/Indexes (SCHEMA_SQL executescript will handle if not exist)
                conn.executescript(SCHEMA_SQL)

                conn.execute("PRAGMA foreign_keys=ON")
                logger.info("Successfully migrated observations table constraints.")
    except Exception as e:
        logger.warning(f"Migration failed or skipped: {e}")
        conn.execute("PRAGMA foreign_keys=ON")

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN materialized_score REAL NOT NULL DEFAULT 1.0")
        from kit.core.memory_policy import MemoryPolicy
        conn.execute(f"""
            UPDATE observations
            SET materialized_score = {MemoryPolicy.SQL_RANKING_FORMULA}
        """)
        logger.info("Migrated: Added materialized_score to observations and backfilled values")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN is_active BOOLEAN DEFAULT 1")
        logger.info("Migrated: Added is_active to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN supersedes_id INTEGER")
        logger.info("Migrated: Added supersedes_id to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_uid ON nodes(uid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_node ON observations(node_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_commit ON observations(commit_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_branch ON observations(branch)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_namespace ON observations(namespace)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_scope_created ON observations(scope, created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_node_scope ON observations(node_id, scope)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_symbol ON observations(symbol)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_obs_active_score ON observations(is_active, materialized_score DESC)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_hash ON observations(structural_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_recall_optimized ON observations(is_active, scope, materialized_score DESC)")

        # Ensure metrics table exists for existing DBs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                signal TEXT,
                scope TEXT,
                outcome TEXT,
                latency_ms REAL,
                message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_event ON metrics(event_type)")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN created_at_bucket INTEGER GENERATED ALWAYS AS (CAST(strftime('%Y%m%d%H', created_at) AS INTEGER)) VIRTUAL")
        logger.info("Migrated: Added created_at_bucket to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_bucket ON observations(created_at_bucket, importance)")
        logger.info("Migrated: Added idx_obs_bucket")
    except sqlite3.OperationalError:
        pass

    # v1.2.4-LOCK: Perception-Cognition split.
    # is_baked=0: Raw Perception | is_baked=1: Verified Truth | is_baked=-1: Toxic/Unanalyzable
    try:
        conn.execute("ALTER TABLE observations ADD COLUMN is_baked INTEGER DEFAULT 0")
        # Backfill: legacy observations are Trusted Legacy Truth.
        conn.execute("UPDATE observations SET is_baked = 1 WHERE is_baked = 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_baked ON observations(is_baked)")
        logger.info("Migrated: Added is_baked; backfilled legacy records as baked.")
    except sqlite3.OperationalError:
        pass

    # v1.2.4-TITANIUM: Standardized Node Type & Status
    try:
        conn.execute("ALTER TABLE nodes ADD COLUMN node_type TEXT DEFAULT 'observation'")
        conn.execute("ALTER TABLE nodes ADD COLUMN status TEXT DEFAULT 'active'")
        conn.execute("ALTER TABLE nodes ADD COLUMN visibility TEXT DEFAULT 'local'")
        
        # Backfill node_type from legacy kind
        conn.execute("UPDATE nodes SET node_type = 'skill' WHERE kind = 'skill'")
        conn.execute("UPDATE nodes SET node_type = 'entity' WHERE kind = 'arch'")
        
        logger.info("Migrated: Added node_type, status, and visibility to nodes")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status)")
    except sqlite3.OperationalError:
        pass

    # v1.2.4-TITANIUM: Vantage Read Optimization
    try:
        conn.execute("""
            CREATE VIEW IF NOT EXISTS baked_observations AS
            SELECT
                id,
                node_id,
                content,
                tag,
                importance,
                created_at,
                structural_hash
            FROM observations
            WHERE is_active = 1
              AND is_baked = 1
              AND superseded_at IS NULL
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_vantage_read ON observations(is_active, is_baked, superseded_at)")
    except sqlite3.OperationalError:
        pass

    # v1.2.4-STAGE5.3: Canonical Memory Model fields
    try:
        conn.execute("ALTER TABLE observations ADD COLUMN is_canonical INTEGER DEFAULT 0")
        logger.info("Migrated: Added is_canonical to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE observations ADD COLUMN canonical_id INTEGER REFERENCES observations(id) ON DELETE SET NULL")
        logger.info("Migrated: Added canonical_id to observations")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_canonical ON observations(canonical_id) WHERE canonical_id IS NOT NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_is_canonical ON observations(is_canonical) WHERE is_canonical = 1")
    except sqlite3.OperationalError:
        pass


    # v1.2.4-STAGE5.5: Symbol Reconciliation Engine (SRE) tables
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                locked INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
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
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_drift_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                metrics_json TEXT DEFAULT '{}',
                final_score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'STABLE',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_reconciliation_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                proposed_symbol TEXT NOT NULL,
                confidence REAL NOT NULL,
                rationale TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_drift_symbol ON symbol_drift_events(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_nodes_symbol ON symbol_nodes(symbol)")
        logger.info("Migrated: Created Stage 5.5 SRE tables")
    except sqlite3.OperationalError as e:
        logger.warning(f"Migration: Failed to create SRE tables: {e}")
    # v1.2.4-TITANIUM: Snapshot Integrity Chain
    try:
        conn.execute("ALTER TABLE snapshots ADD COLUMN parent_hash TEXT")
        conn.execute("ALTER TABLE snapshots ADD COLUMN snapshot_hash TEXT")
        logger.info("Migrated: Added parent_hash and snapshot_hash to snapshots (Integrity Chain)")
    except sqlite3.OperationalError:
        pass

    # Backfill symbol_nodes from existing locked symbols
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


def enable_wal(conn: sqlite3.Connection):
    """Activate high-performance mode (v1.2.4-TITANIUM Tuning)."""
    # 1. Concurrency Mode
    mode_row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    if mode_row:
        mode = mode_row[0] if isinstance(mode_row, tuple) else mode_row["journal_mode"]
        if mode.lower() != "wal":
            logger.warning(f"Failed to enable WAL mode. Current mode: {mode}")

    # 2. Performance Pragmas
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    
    # 3. Memory & I/O Optimization (TUNE MEMORY)
    # Use Memory-Mapped I/O for faster reads (up to 256MB)
    conn.execute("PRAGMA mmap_size=268435456") 
    # Use RAM for temporary tables/indexes
    conn.execute("PRAGMA temp_store=MEMORY")
    # Larger cache (approx 64MB)
    conn.execute("PRAGMA cache_size=-64000")
    # Read-uncommitted for maximum throughput where appropriate
    conn.execute("PRAGMA read_uncommitted=1")
