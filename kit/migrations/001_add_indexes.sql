-- migration: 001_add_indexes.sql
-- Optimizes Graph Traversal for 10M+ edges
CREATE INDEX IF NOT EXISTS idx_calls_source ON calls(source);
CREATE INDEX IF NOT EXISTS idx_calls_target ON calls(target);
