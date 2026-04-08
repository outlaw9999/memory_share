import logging
import sqlite3

logger = logging.getLogger("kit.schema")


def quote_identifier(identifier: str) -> str:
    """Quote a SQLite identifier defensively."""
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,
    kind TEXT,
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
    tag TEXT CHECK(tag IN ('invariant', 'decision', 'preference', 'note', 'legacy', 'friction')) DEFAULT 'decision',
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
    structural_hash TEXT,
    metadata TEXT DEFAULT '{}',
    commit_id TEXT,
    is_active BOOLEAN DEFAULT 1,
    supersedes_id INTEGER DEFAULT NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (commit_id) REFERENCES commits(id),
    FOREIGN KEY (supersedes_id) REFERENCES observations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_created ON observations(created_at);

CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
    content,
    content='observations',
    content_rowid='id',
    tokenize='porter'
);

-- FTS Triggers
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
"""


def init_db(conn: sqlite3.Connection):
    """Bootstrap or migrate the database schema."""
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
        conn.execute("ALTER TABLE observations ADD COLUMN agent_id TEXT")
        logger.info("Migrated: Added agent_id to observations")
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

    # Tag migration (v1.2.3): Expand allowed tags to include 'note' and 'legacy'
    try:
        # Check if the constraint is old
        cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='observations'")
        row = cur.fetchone()
        if row:
            schema_sql = row[0]
            if "legacy" not in schema_sql or "note" not in schema_sql or "friction" not in schema_sql:
                logger.info("Migrating observations table to expand tag constraints (v1.2.3.3)...")
                # Standard SQLite table migration pattern
                conn.execute("PRAGMA foreign_keys=OFF")

                # 1. Create new table with updated schema (using temporary name)
                # We need to extract the CREATE TABLE statement for observations from SCHEMA_SQL but with a new name
                # Actually, simpler to just run the create statement directly
                new_table_sql = """
                CREATE TABLE observations_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    layer TEXT CHECK(layer IN ('working', 'episodic', 'semantic', 'procedural')) DEFAULT 'episodic',
                    tag TEXT CHECK(tag IN ('invariant', 'decision', 'preference', 'note', 'legacy', 'friction')) DEFAULT 'decision',
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
                    structural_hash TEXT,
                    metadata TEXT DEFAULT '{}',
                    commit_id TEXT, agent_id TEXT, 
                    is_active BOOLEAN DEFAULT 1,
                    supersedes_id INTEGER,
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (commit_id) REFERENCES commits(id)
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
        # Backfill scores for existing records
        conn.execute("""
            UPDATE observations
            SET materialized_score = importance * ((access_count + 1) / (access_count + 5.0)) * 
            CASE layer WHEN 'working' THEN 3.0 WHEN 'episodic' THEN 2.0 WHEN 'semantic' THEN 1.5 ELSE 1.0 END
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


def enable_wal(conn: sqlite3.Connection):
    """Activate high-performance mode."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
