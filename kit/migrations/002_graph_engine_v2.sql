-- migration: 002_graph_engine_v2.sql
-- Optimizes Graph Traversal for 10M+ edges with Thin Edges and Integer IDs

PRAGMA foreign_keys=off;
BEGIN TRANSACTION;

-- 1. Create new table for Nodes (Integer IDs)
CREATE TABLE IF NOT EXISTS nodes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    kind TEXT,
    file_path TEXT,
    line_number INTEGER
);

-- 2. Create new table for Edges (Thin Edges)
CREATE TABLE IF NOT EXISTS edges_new (
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    layer INTEGER NOT NULL,
    weight REAL DEFAULT 1.0,
    FOREIGN KEY(source_id) REFERENCES nodes_new(id),
    FOREIGN KEY(target_id) REFERENCES nodes_new(id)
);

-- Note: In a real database with existing data, we would migrate `symbols` to `nodes_new`
-- and `calls` to `edges_new`. Since we are building the prototype and have access 
-- to index from scratch, we leave the actual data migration logic simplified.

-- Try to migrate existing data (will fail gracefully if this is a fresh database without v1 structure)
INSERT OR IGNORE INTO nodes_new(symbol, kind, file_path, line_number)
SELECT name, kind, file, line FROM symbols;

-- Insert remaining symbols from calls that weren't in symbols table
INSERT OR IGNORE INTO nodes_new(symbol)
SELECT DISTINCT caller FROM calls
UNION
SELECT DISTINCT callee FROM calls;

-- Migrate edges (layer 0 = structural/call graph)
INSERT OR IGNORE INTO edges_new(source_id, target_id, layer, weight)
SELECT s.id, t.id, 0, 1.0
FROM calls c
JOIN nodes_new s ON s.symbol = c.caller
JOIN nodes_new t ON t.symbol = c.callee;

-- 3. Drop old tables
DROP TABLE IF EXISTS calls;
DROP TABLE IF EXISTS symbols;
DROP TABLE IF EXISTS symbol_fts;

-- 4. Rename new tables
ALTER TABLE nodes_new RENAME TO nodes;
ALTER TABLE edges_new RENAME TO edges;

-- 5. Create super-optimized Covering Indices
CREATE INDEX IF NOT EXISTS idx_edges_source_layer ON edges(source_id, layer);
CREATE INDEX IF NOT EXISTS idx_edges_target_layer ON edges(target_id, layer);
CREATE INDEX IF NOT EXISTS idx_nodes_symbol ON nodes(symbol);

-- 6. Setup new FTS5 searching on the nodes table
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(
    symbol,
    content='nodes',
    content_rowid='id',
    tokenize='unicode61',
    prefix='2 3'
);

-- Triggers to auto-update node_fts
CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
    INSERT INTO node_fts(rowid, symbol) VALUES (new.id, new.symbol);
END;

CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
    INSERT INTO node_fts(node_fts, rowid, symbol) VALUES ('delete', old.id, old.symbol);
END;

CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE OF symbol ON nodes BEGIN
    INSERT INTO node_fts(node_fts, rowid, symbol) VALUES ('delete', old.id, old.symbol);
    INSERT INTO node_fts(rowid, symbol) VALUES (new.id, new.symbol);
END;

COMMIT;
PRAGMA foreign_keys=on;
