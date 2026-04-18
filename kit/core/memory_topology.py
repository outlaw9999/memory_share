# kit/core/memory_topology.py
# v1.2.3.9 — Memory Topology Layer (Single Source of Truth)
#
# CRITICAL: This module defines WHERE memory lives (physical topology).
# This is NOT an implementation detail — it's part of the system contract.
#
# Philosophy:
#   GLOBAL memory = user home directory (shared across all projects)
#   LOCAL memory = project root (per-project, isolated)
#
# No hardcoded paths elsewhere. All path resolution goes through this layer.

import logging
import sqlite3
from pathlib import Path
from typing import Optional, Literal

logger = logging.getLogger("kit.memory_topology")


class MemoryScope:
    """Memory scope identifier."""
    GLOBAL = "global"
    LOCAL = "local"


class MemoryTopology:
    """
    Single source of truth for memory physical topology.
    
    Defines where each tier's database files live.
    
    INVARIANT:
    - GLOBAL memory: ~/.kit/ (shared system state)
    - LOCAL memory: <project_root>/.kit/ (per-project state)
    """
    
    # System-level shared directory (home)
    GLOBAL_KIT_HOME = Path.home() / ".kit"
    
    # Database filenames (consistent across all scopes)
    DB_LOCAL = "local_brain.db"
    DB_GLOBAL = "global_brain.db"
    DB_FROZEN = "global_read_only.db"
    DB_SNAPSHOT = "memory_snapshot.db"
    DB_ROUTING_AUDIT = "router_decisions.jsonl"
    DB_TELEMETRY = "routing_telemetry.jsonl"
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize topology for a given project.
        
        Args:
            project_root: Path to the project root directory.
                         If None, only GLOBAL scope is available.
        """
        self.project_root = project_root
        self.local_kit_home = (project_root / ".kit") if project_root else None
        
        logger.info(f"MemoryTopology initialized")
        logger.info(f"  GLOBAL: {self.GLOBAL_KIT_HOME}")
        if self.local_kit_home:
            logger.info(f"  LOCAL: {self.local_kit_home}")
    
    def resolve(
        self,
        scope: Literal["global", "local"],
        db_type: str = "local",
    ) -> Path:
        """
        Resolve the path to a memory database.
        
        Args:
            scope: "global" or "local"
            db_type: "local", "global", "frozen", "snapshot", or other valid DB name
        
        Returns:
            Absolute path to the database file
        
        Raises:
            ValueError: If scope is invalid or LOCAL requested without project_root
        """
        
        if scope not in [MemoryScope.GLOBAL, MemoryScope.LOCAL]:
            raise ValueError(f"Invalid scope: {scope}. Must be 'global' or 'local'.")
        
        if scope == MemoryScope.LOCAL:
            if not self.local_kit_home:
                raise ValueError(
                    "Cannot resolve LOCAL path: project_root not set. "
                    "Initialize MemoryTopology with project_root."
                )
            base_dir = self.local_kit_home
        else:  # GLOBAL
            base_dir = self.GLOBAL_KIT_HOME
        
        # Map db_type to filename
        if db_type == "local":
            filename = self.DB_LOCAL
        elif db_type == "global":
            filename = self.DB_GLOBAL
        elif db_type == "frozen":
            filename = self.DB_FROZEN
        elif db_type == "snapshot":
            filename = self.DB_SNAPSHOT
        elif db_type == "telemetry":
            filename = self.DB_TELEMETRY
        elif db_type == "audit":
            filename = self.DB_ROUTING_AUDIT
        else:
            # Allow custom filenames
            filename = db_type
        
        path = base_dir / filename
        
        logger.debug(f"Resolved {scope}/{db_type} -> {path}")
        
        return path
    
    def get_all_paths(
        self,
        scope: Literal["global", "local"],
    ) -> dict[str, Path]:
        """
        Get all standard database paths for a scope.
        
        Returns:
            Dictionary mapping db_type -> absolute path
        """
        db_types = ["local", "global", "frozen", "snapshot", "telemetry", "audit"]
        
        return {
            db_type: self.resolve(scope, db_type)
            for db_type in db_types
        }
    
    def verify_scope_isolation(self) -> dict[str, bool]:
        """
        Verify that GLOBAL and LOCAL scopes don't overlap.
        
        Returns:
            Dictionary of checks and their results
        """
        checks = {}
        
        # Check 1: LOCAL kit home should not be inside GLOBAL kit home
        if self.local_kit_home:
            is_subpath = str(self.local_kit_home).startswith(str(self.GLOBAL_KIT_HOME))
            checks["local_not_inside_global"] = not is_subpath
            
            if is_subpath:
                logger.error(
                    f"TOPOLOGY VIOLATION: LOCAL kit ({self.local_kit_home}) "
                    f"is inside GLOBAL kit ({self.GLOBAL_KIT_HOME})"
                )
        
        # Check 2: Different base directories
        if self.local_kit_home:
            checks["different_root_dirs"] = (
                self.local_kit_home.parent != self.GLOBAL_KIT_HOME.parent
            )
        
        return checks
    
    def initialize_scope(self, scope: Literal["global", "local"]) -> Path:
        """
        Initialize directory structure for a scope.
        
        Creates .kit directory if it doesn't exist.
        
        Returns:
            Path to the initialized kit directory
        """
        if scope == MemoryScope.GLOBAL:
            kit_dir = self.GLOBAL_KIT_HOME
        elif scope == MemoryScope.LOCAL:
            if not self.local_kit_home:
                raise ValueError("Cannot initialize LOCAL: project_root not set")
            kit_dir = self.local_kit_home
        else:
            raise ValueError(f"Invalid scope: {scope}")
        
        kit_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized {scope} kit directory: {kit_dir}")
        
        return kit_dir

    def connect(
        self,
        scope: Literal["global", "local"],
        db_type: str = "local",
        timeout: float = 10.0,
        readonly: bool = False,
    ) -> sqlite3.Connection:
        """
        Authority Pattern: Single point of entry for SQLite connections.

        Enforces production-grade PRAGMAs and physical locks:
        - WAL mode
        - Synchronous NORMAL
        - Foreign Key enforcement
        - Busy timeout
        - mode=ro for Frozen/Snapshot Tier (Physical Lock)
        """
        path = self.resolve(scope, db_type)

        # Ensure directory exists before connecting
        path.parent.mkdir(parents=True, exist_ok=True)

        is_frozen = db_type == "frozen"
        is_snapshot = db_type == "snapshot"
        is_readonly = is_frozen or readonly or is_snapshot
        uri = f"file:{path.as_posix()}?mode=ro" if is_readonly else f"file:{path.as_posix()}"

        try:
            conn = sqlite3.connect(
                uri,
                uri=True,
                timeout=timeout,
                check_same_thread=False,
                isolation_level=None,  # Standard KIT behavior: WAL + Manual Tx
            )
            conn.row_factory = sqlite3.Row

            # --- PRAGMA Architecture Lock ---
            if not is_readonly:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
            else:
                conn.execute("PRAGMA query_only=ON")
            
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")

            return conn
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to {path}: {e}")
            raise


class MemoryTopologyFactory:
    """Factory for creating properly-configured MemoryTopology instances."""
    
    @staticmethod
    def for_project(project_root: Path) -> MemoryTopology:
        """Create topology for a project (with both GLOBAL and LOCAL scopes)."""
        topology = MemoryTopology(project_root=project_root)
        
        # Initialize both scopes
        topology.initialize_scope("global")
        topology.initialize_scope("local")
        
        # Verify separation
        checks = topology.verify_scope_isolation()
        for check_name, result in checks.items():
            if not result:
                logger.warning(f"Scope isolation check '{check_name}' failed")
        
        return topology
    
    @staticmethod
    def global_only() -> MemoryTopology:
        """Create topology for GLOBAL scope only (no project context)."""
        topology = MemoryTopology(project_root=None)
        topology.initialize_scope("global")
        return topology


# ============================================================================
# VALIDATION & TESTING
# ============================================================================

if __name__ == "__main__":
    import tempfile
    
    print("\n" + "="*70)
    print("[*] Memory Topology - Validation")
    print("="*70 + "\n")
    
    # Test 1: GLOBAL only
    print("[1] GLOBAL-only scope:")
    global_topo = MemoryTopologyFactory.global_only()
    print(f"  Global kit home: {global_topo.GLOBAL_KIT_HOME}")
    print(f"  Global db path: {global_topo.resolve('global', 'global')}")
    print(f"  Global frozen path: {global_topo.resolve('global', 'frozen')}")
    
    # Test 2: Project with LOCAL scope
    print("\n[2] Project with LOCAL scope:")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        proj_topo = MemoryTopologyFactory.for_project(project_root)
        
        print(f"  Project root: {project_root}")
        print(f"  Global kit home: {proj_topo.GLOBAL_KIT_HOME}")
        print(f"  Local kit home: {proj_topo.local_kit_home}")
        
        # Verify isolation
        checks = proj_topo.verify_scope_isolation()
        print(f"  Isolation checks:")
        for check, result in checks.items():
            status = "[OK]" if result else "[FAIL]"
            print(f"    {status} {check}")
        
        # Get all paths
        print(f"\n  LOCAL paths:")
        local_paths = proj_topo.get_all_paths("local")
        for db_type, path in local_paths.items():
            print(f"    {db_type}: {path}")
        
        print(f"\n  GLOBAL paths:")
        global_paths = proj_topo.get_all_paths("global")
        for db_type, path in global_paths.items():
            print(f"    {db_type}: {path}")
    
    # Test 3: Error handling
    print("\n[3] Error handling:")
    try:
        topo = MemoryTopology(project_root=None)
        topo.resolve("local", "local")  # Should fail
        print("  [FAIL] Should have raised ValueError")
    except ValueError as e:
        print(f"  [OK] Correctly rejected LOCAL without project_root: {str(e)[:50]}...")
    
    print("\n" + "="*70)
    print("[OK] Topology validation complete")
    print("="*70 + "\n")
