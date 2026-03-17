import sys
import shutil
import sqlite3
from pathlib import Path
from kit.core.kit_cognitive_core import SAMBrain

def normalize_for_dedup(text: str) -> str:
    import re
    # Remove punctuation and normalize whitespace
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()

def run_doctor(brain: SAMBrain, mode: str = "safe"):
    print(f"🏥 AI Kernel Health Check (Mode: {mode})", file=sys.stderr)
    
    # 1. Backup DB
    db_path = brain.db_path
    backup_path = db_path.with_name("brain.db.bak")
    try:
        shutil.copy2(db_path, backup_path)
        print(f"💾 Backup created: {backup_path.name}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ Warning: Could not create backup: {e}", file=sys.stderr)
    
    # 2. Prune Noise
    with brain._get_connection() as conn:
        print("🧹 Running Cognitive Pruning...", file=sys.stderr)
        # Aggressive mode: Clean old working/episodic facts
        if mode == "aggressive":
            cutoff_days = 30
            low_access = 1
            # Hard delete
            cur = conn.execute(f"""
                DELETE FROM observations 
                WHERE layer IN ('working', 'episodic')
                  AND access_count <= ?
                  AND tag = 'decision'
                  AND JULIANDAY('now') - JULIANDAY(created_at) > ?
            """, (low_access, cutoff_days))
            pruned_count = cur.rowcount
            if pruned_count > 0:
                print(f"   - Permanently removed {pruned_count} decayed facts.", file=sys.stderr)
        else:
            # Safe mode: just mark as superseded
            cutoff_days = 90
            low_access = 0
            cur = conn.execute(f"""
                UPDATE observations SET superseded_at = CURRENT_TIMESTAMP
                WHERE layer IN ('working', 'episodic')
                  AND access_count <= ?
                  AND tag = 'decision'
                  AND superseded_at IS NULL
                  AND JULIANDAY('now') - JULIANDAY(created_at) > ?
            """, (low_access, cutoff_days))
            pruned_count = cur.rowcount
            if pruned_count > 0:
                print(f"   - Soft-pruned {pruned_count} decayed facts.", file=sys.stderr)
            
        # 3. Deduplication (Safe exact/normalized string match)
        print("🧬 Running Fact Deduplication...", file=sys.stderr)
        rows = conn.execute("""
            SELECT id, content, scope, layer, importance, access_count, tag
            FROM observations
            WHERE superseded_at IS NULL
            ORDER BY created_at ASC
        """).fetchall()
        
        seen = {} # sig -> id
        merged_count = 0
        
        for row in rows:
            norm_content = normalize_for_dedup(row["content"])
            scope = row["scope"] or ""
            layer = row["layer"] or ""
            tag = row["tag"] or ""
            
            # Exact Match Level 1 + Level 2 (Normalized String)
            sig = f"{norm_content}|{scope}|{layer}|{tag}"
            
            if sig in seen:
                # Merge into existing
                keep_id = seen[sig]
                drop_id = row["id"]
                conn.execute("UPDATE observations SET superseded_at = CURRENT_TIMESTAMP WHERE id = ?", (drop_id,))
                conn.execute("UPDATE observations SET access_count = access_count + ? WHERE id = ?", (row["access_count"] + 1, keep_id))
                merged_count += 1
            else:
                seen[sig] = row["id"]
                
        if merged_count > 0:
            print(f"   - Merged {merged_count} duplicate facts safely.", file=sys.stderr)
            
        # 4. De-fragmentation
        print("🗄️ Optimizing Storage...", file=sys.stderr)
        conn.execute("VACUUM")
        conn.execute("PRAGMA optimize")
        
    print("✅ Doctor complete. System is healthy.", file=sys.stderr)
