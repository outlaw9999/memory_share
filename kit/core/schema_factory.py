import sqlite3
import logging

logger = logging.getLogger("kit.schema")

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

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    layer TEXT CHECK(layer IN ('working', 'episodic', 'semantic', 'procedural')) DEFAULT 'episodic',
    importance REAL DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    superseded_at DATETIME,
    last_accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
    content,
    content='observations',
    content_rowid='id'
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
"""

def init_db(conn: sqlite3.Connection):
    """Bootstrap or migrate the database schema."""
    conn.executescript(SCHEMA_SQL)
    
    # Migration: Ensure superseded_at exists in observations (Chronos Patch)
    try:
        conn.execute("ALTER TABLE observations ADD COLUMN superseded_at DATETIME")
        logger.info("Migrated: Added superseded_at to observations")
    except sqlite3.OperationalError:
        # Column already exists
        pass

def enable_wal(conn: sqlite3.Connection):
    """Activate high-performance mode."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
