-- ============================================================================
-- Kit v1.2.4 - Cognitive Relational Graph Migration (PATCHED)
-- ============================================================================
-- Status: DESIGN SEED (For post-Desert Mode)
-- Fixes: Race conditions in triggers & CTE query optimization
-- ============================================================================

-- 1. PERFORMANCE TUNING
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- ==========================================
-- LAYER 1: COGNITIVE NODES & EDGES (DNA)
-- ==========================================
CREATE TABLE IF NOT EXISTS cognitive_nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,             -- 'auth', 'crypto', 'sql', 'ui'
    symbol_id TEXT NOT NULL UNIQUE, -- Absolute identifier from Vantage
    invariant_rule TEXT,        
    created_at INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS cognitive_edges (
    source_id TEXT NOT NULL REFERENCES cognitive_nodes(id),
    target_id TEXT NOT NULL REFERENCES cognitive_nodes(id),
    weight REAL NOT NULL DEFAULT 1.0,
    relation TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id)
) STRICT;

-- ==========================================
-- LAYER 2: VANTAGE SENSORS (STATE MACHINE)
-- ==========================================
-- Managing Vantage run lifecycles to prevent race conditions
CREATE TABLE IF NOT EXISTS vantage_runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,           -- 'pending', 'completed'
    timestamp INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS vantage_run_signals (
    run_id TEXT NOT NULL REFERENCES vantage_runs(run_id),
    symbol_id TEXT NOT NULL,    
    kind TEXT NOT NULL,
    PRIMARY KEY (run_id, symbol_id)
) STRICT;

-- ==========================================
-- LAYER 3: FRICTION LOGS (SHADOW AUDIT)
-- ==========================================
CREATE TABLE IF NOT EXISTS friction_logs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES vantage_runs(run_id),
    timestamp INTEGER NOT NULL,
    miss_type TEXT NOT NULL,    
    severity TEXT NOT NULL,     
    details TEXT NOT NULL
) STRICT;

-- ==========================================
-- LAYER 4: SHADOW MODE TRIGGERS (BATCH-PROCESS)
-- ==========================================
-- Only fires when run status is explicitly 'completed' to avoid partial evaluation.
CREATE TRIGGER IF NOT EXISTS shadow_auth_crypto_miss
AFTER UPDATE OF status ON vantage_runs
WHEN NEW.status = 'completed'
-- Check: Does it have 'auth' symbols?
AND EXISTS (
    SELECT 1 FROM vantage_run_signals vrs
    JOIN cognitive_nodes cn ON vrs.symbol_id = cn.symbol_id
    WHERE vrs.run_id = NEW.run_id AND cn.type = 'auth'
)
-- Check: But MISSING 'crypto' symbols?
AND NOT EXISTS (
    SELECT 1 FROM vantage_run_signals vrs
    JOIN cognitive_nodes cn ON vrs.symbol_id = cn.symbol_id
    WHERE vrs.run_id = NEW.run_id AND cn.type = 'crypto'
)
BEGIN
    INSERT INTO friction_logs (id, run_id, timestamp, miss_type, severity, details)
    VALUES (
        hex(randomblob(8)), NEW.run_id, strftime('%s', 'now'), 
        'Auth_Crypto_Near_Miss', 'HIGH',
        'Vantage detected changes in Auth (Type-Matched) but missing Cryptography invariants.'
    );
END;
