import logging
import sqlite3
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("kit.sealing")

# v1.2.4-TITANIUM: Canonical Kernel Constitution
SEALED_VERSION = "1.2.4-sealed"
REQUIRED_POLICIES = {
    "integrity_policy": "strict",
    "write_authority": "MemoryRouter"
}

class KernelSealError(Exception):
    """Raised when the kernel constitution is violated (v1.2.4-TITANIUM)."""
    pass

def verify_kernel_seal(db_path: Path) -> Dict[str, str]:
    """
    Verify that the database adheres to the v1.2.4-sealed contract.
    """
    if not db_path.exists():
        return {"status": "missing", "reason": f"Database not found at {db_path}"}

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        
        # 1. Check version
        row = conn.execute("SELECT value FROM kernel_metadata WHERE key = 'version'").fetchone()
        if not row:
            raise KernelSealError("Kernel version metadata missing.")
            
        version = row["value"]
        if version != SEALED_VERSION:
            raise KernelSealError(f"Schema mismatch: Expected {SEALED_VERSION}, found {version}")
            
        # 2. Check policies
        metadata = {}
        rows = conn.execute("SELECT key, value FROM kernel_metadata").fetchall()
        for r in rows:
            metadata[r["key"]] = r["value"]
            
        for policy, expected in REQUIRED_POLICIES.items():
            if metadata.get(policy) != expected:
                raise KernelSealError(f"Policy violation: {policy} must be '{expected}'")
                
        conn.close()
        return {"status": "sealed", "version": version, "policies": "enforced"}
        
    except sqlite3.OperationalError as e:
        if "no such table: kernel_metadata" in str(e):
             return {"status": "unsealed", "reason": "Legacy schema (pre-v1.2.4-sealed)"}
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        return {"status": "violated", "reason": str(e)}

def seal_kernel(db_path: Path):
    """
    Hard-seal the kernel by injecting the v1.2.4 constitution.
    """
    logger.info(f"Sealing kernel at {db_path} (SPEC {SEALED_VERSION})...")
    conn = sqlite3.connect(db_path)
    try:
        # Ensure schema is up to date (v1.2.4-TITANIUM)
        from kit.core.schema_factory import init_db
        init_db(conn)
        
        # Enforce Sealing Metadata
        conn.execute("INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES ('version', ?)", (SEALED_VERSION,))
        for key, val in REQUIRED_POLICIES.items():
            conn.execute("INSERT OR REPLACE INTO kernel_metadata (key, value) VALUES (?, ?)", (key, val))
            
        conn.commit()
        logger.info("Kernel successfully sealed.")
    finally:
        conn.close()
