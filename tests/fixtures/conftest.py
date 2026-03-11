"""
Production-Ready Mock Database Fixtures for .kit V2 Testing

This module provides in-memory SQLite databases that mirror the exact
production schema. The mock data includes a deliberate cycle (utils -> billing -> auth -> utils)
to test Drift Detector and Graph Traversal.

Schema matches: kit/core/graph_store.py
"""

import pytest
import sqlite3
from pathlib import Path


@pytest.fixture
def mock_atlas_db():
    """
    In-Memory SQLite Database reflecting Production Code Graph.
    
    Module structure:
    ├─ cli (entry point)
    ├─ auth (authentication)
    ├─ utils (shared utilities)
    └─ billing (payment processing)
    
    Dependencies:
    cli → auth
    auth → utils
    billing → auth
    utils → billing  (CYCLE: creates semantic drift for testing)
    """
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    
    # ============== TABLE 1: Symbols (Code entities) ==============
    cur.execute("""
        CREATE VIRTUAL TABLE symbols USING fts5(
            name,         -- function/class name
            kind UNINDEXED,    -- 'function', 'class', 'method', 'module'
            module UNINDEXED,  -- module name (auth, billing, etc)
            file UNINDEXED,    -- file path
            line UNINDEXED     -- line number
        )
    """)
    
    symbols_data = [
        # CLI module
        ("main", "function", "cli", "cli/main.py", 10),
        ("parse_args", "function", "cli", "cli/main.py", 30),
        
        # Auth module
        ("login", "function", "auth", "auth/service.py", 25),
        ("logout", "function", "auth", "auth/service.py", 45),
        ("verify_token", "function", "auth", "auth/service.py", 60),
        ("SessionManager", "class", "auth", "auth/session.py", 15),
        
        # Utils module
        ("hash_string", "function", "utils", "utils/crypto.py", 15),
        ("encrypt", "function", "utils", "utils/crypto.py", 40),
        ("Logger", "class", "utils", "utils/logging.py", 10),
        
        # Billing module
        ("charge_card", "function", "billing", "billing/payment.py", 30),
        ("process_invoice", "function", "billing", "billing/invoice.py", 50),
        ("PaymentGateway", "class", "billing", "billing/gateway.py", 20)
    ]
    cur.executemany(
        "INSERT INTO symbols VALUES (?, ?, ?, ?, ?)", 
        symbols_data
    )
    
    # ============== TABLE 2: Calls (Function-level calls) ==============
    cur.execute("""
        CREATE TABLE calls (
            caller TEXT,
            callee TEXT,
            caller_module TEXT,
            callee_module TEXT,
            PRIMARY KEY(caller, callee)
        )
    """)
    
    calls_data = [
        # cli -> auth
        ("main", "login", "cli", "auth"),
        ("parse_args", "login", "cli", "auth"),
        
        # auth -> utils
        ("login", "hash_string", "auth", "utils"),
        ("verify_token", "hash_string", "auth", "utils"),
        
        # billing -> auth
        ("charge_card", "verify_token", "billing", "auth"),
        
        # utils -> billing (CYCLE EDGE)
        ("encrypt", "process_invoice", "utils", "billing")
    ]
    cur.executemany(
        "INSERT INTO calls VALUES (?, ?, ?, ?)", 
        calls_data
    )
    
    # ============== TABLE 3: Module Edges (for Distance Cache) ==============
    cur.execute("""
        CREATE TABLE module_edges (
            from_module TEXT,
            to_module TEXT,
            UNIQUE(from_module, to_module)
        )
    """)
    
    edges_data = [
        ("cli", "auth"),
        ("auth", "utils"),
        ("billing", "auth"),
        ("utils", "billing")  # CREATES CYCLE: utils -> billing -> auth -> utils
    ]
    cur.executemany(
        "INSERT INTO module_edges VALUES (?, ?)", 
        edges_data
    )
    
    # ============== TABLE 4: Module Distances Cache ==============
    # Pre-computed distances (simulating lazy-evaluated cache)
    cur.execute("""
        CREATE TABLE module_distances (
            module_a TEXT,
            module_b TEXT,
            distance INT,
            UNIQUE(module_a, module_b)
        )
    """)
    
    distances_data = [
        # Same module
        ("cli", "cli", 0),
        ("auth", "auth", 0),
        ("utils", "utils", 0),
        ("billing", "billing", 0),
        
        # Distances
        ("cli", "auth", 1),
        ("cli", "utils", 2),
        ("cli", "billing", 2),
        
        ("auth", "utils", 1),
        ("auth", "billing", 2),
        
        ("billing", "auth", 1),
        ("billing", "utils", 2),
        
        ("utils", "billing", 1),
        ("utils", "auth", 2),
        ("utils", "cli", 3)
    ]
    cur.executemany(
        "INSERT INTO module_distances VALUES (?, ?, ?)", 
        distances_data
    )
    
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_memory_db():
    """
    In-Memory SQLite Database reflecting Neural Memory + Bridges.
    
    Used for testing:
    - Bridge generation
    - Memory search via bridges
    - Orphan symbol detection
    """
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    
    # ============== TABLE 1: Neural Memory ==============
    cur.execute("""
        CREATE TABLE neural_memory (
            id TEXT PRIMARY KEY,
            content TEXT,
            metadata TEXT
        )
    """)
    
    memory_data = [
        ("mem_1", "AuthService.login uses JWT tokens for session management", "{}"),
        ("mem_2", "utils.hash_string applies SHA-256 with salt", "{}"),
        ("mem_3", "Deprecated: old_payment_gateway was replaced by PaymentGateway class", "{}"),
        ("mem_4", "billing module should not directly call auth internals", "{}")
    ]
    cur.executemany(
        "INSERT INTO neural_memory VALUES (?, ?, ?)", 
        memory_data
    )
    
    # ============== TABLE 2: Bridges (Memory ↔ Code Linking) ==============
    cur.execute("""
        CREATE TABLE bridges (
            id INTEGER PRIMARY KEY,
            memory_id TEXT,
            symbol_name TEXT,
            symbol_kind TEXT,
            relation_type TEXT,
            confidence REAL,
            status TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    
    bridges_data = [
        # Active bridges
        (1, "mem_1", "login", "function", "mentions", 0.95, "active", "2026-03-01", "2026-03-01"),
        (2, "mem_2", "hash_string", "function", "explains", 0.90, "active", "2026-03-02", "2026-03-02"),
        (3, "mem_4", "charge_card", "function", "violates", 0.85, "active", "2026-03-03", "2026-03-03"),
        
        # Orphan bridge (for drift detection)
        (4, "mem_3", "old_payment_gateway", "function", "explains", 0.80, "orphan", "2026-02-15", "2026-03-01")
    ]
    cur.executemany(
        """INSERT INTO bridges 
           (id, memory_id, symbol_name, symbol_kind, relation_type, confidence, status, created_at, updated_at) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        bridges_data
    )
    
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_module_graph():
    """
    Simple Python dict representing module dependency graph.
    Useful for testing cycle detection without SQLite queries.
    """
    return {
        "cli": ["auth"],
        "auth": ["utils"],
        "billing": ["auth"],
        "utils": ["billing"]  # Creates cycle
    }
