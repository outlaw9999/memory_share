#!/usr/bin/env python3
"""
Phase 10 Migration Executor

Safe execution with backup, migration, and verification.
Rollback mechanism: backup remains if anything fails.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime
from plugins.atlas_indexer.migration_phase10 import migrate_to_phase10


def run_migration_safe(db_path: str | Path) -> bool:
    """
    Execute Phase 10 migration with safety checks and backup.
    
    Process:
    1. Verify database exists
    2. Create backup (rollback point)
    3. Run migration
    4. Verify migration succeeded (can reconnect to DB)
    5. Report success/failure
    
    The backup is never deleted - it serves as explicit rollback point.
    """
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    # Create backup with timestamp
    backup_path = db_path.with_suffix(f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    
    print(f"📦 Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"   ✅ Backup ready (use to rollback if needed)")
    
    try:
        print(f"\n🔄 Starting Phase 10 migration...")
        print(f"   Schema: text-based (name) → identity-based (symbol_id)")
        
        success = migrate_to_phase10(db_path)
        
        if success:
            # Verify database is valid by attempting connection
            import sqlite3
            conn = sqlite3.connect(db_path)
            
            # Quick sanity check
            cur = conn.cursor()
            symbol_count = cur.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
            calls_count = cur.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            
            conn.close()
            
            print(f"\n✅ Phase 10 migration SUCCEEDED!")
            print(f"\n   Database state:")
            print(f"     • symbols: {symbol_count} rows (identity-based)")
            print(f"     • calls: {calls_count} rows (ID references)")
            print(f"     • Backup: {backup_path}")
            print(f"\n   Next step: Run 'pytest' to verify all tests pass")
            
            return True
        else:
            print(f"\n❌ Phase 10 migration FAILED")
            print(f"   Rollback: Restore from {backup_path}")
            return False
            
    except Exception as e:
        print(f"\n❌ Phase 10 migration ERROR: {e}")
        print(f"   Rollback: Restore from {backup_path}")
        print(f"   Example: cp {backup_path} {db_path}")
        return False


if __name__ == "__main__":
    # Find the .kit database
    workspace_root = Path(__file__).parent.parent.parent
    kit_db = workspace_root / ".antigravity" / "atlas" / "atlas.db"
    
    print("=" * 70)
    print("🛡️  PHASE 10: IDENTITY MIGRATION (SAFE EXECUTION)")
    print("=" * 70)
    print()
    
    success = run_migration_safe(kit_db)
    
    sys.exit(0 if success else 1)
