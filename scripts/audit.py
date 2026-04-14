import sqlite3
import json
import os
import sys
from pathlib import Path

# Target: v1.2.4-TITANIUM Canonical Auditor
# Domain Taxonomy: ENVIRONMENT, EXECUTION, MEMORY, SEARCH, SKILL, UX

def get_db_stats(db_path):
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    stats = {
        "nodes": c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
        "observations": c.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
        "active_observations": c.execute("SELECT COUNT(*) FROM observations WHERE is_active = 1").fetchone()[0],
    }
    conn.close()
    return stats

def find_friction_points(db_path, source):
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Broad search for potential friction
    sql = """
        SELECT o.id, n.uid, o.tag, o.content, o.created_at, o.is_active, o.metadata
        FROM observations o
        JOIN nodes n ON o.node_id = n.id
        WHERE o.tag IN ('friction', 'issue', 'bug', 'fail', 'error')
           OR n.uid LIKE '%friction%'
           OR o.content LIKE '%friction%'
           OR o.content LIKE '%problem%'
           OR o.content LIKE '%symptom%'
           OR o.content LIKE '%pain%'
           OR o.content LIKE '%fail%'
           OR o.content LIKE '%error%'
           OR o.content LIKE '%broken%'
        ORDER BY o.created_at DESC
    """
    
    rows = c.execute(sql).fetchall()
    data = []
    for r in rows:
        content = r['content']
        # Extract existing taxonomy if present (backward compatibility)
        d = dict(r)
        d['source'] = source
        d['is_active'] = bool(r['is_active'])
        data.append(d)
    conn.close()
    return data

def main():
    # Ensure UTF-8 output
    if sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    project_db = '.kit/brain.db'
    global_db = os.path.join(os.path.expanduser('~'), '.kit', 'global.db')
    
    report = {
        "project_stats": get_db_stats(project_db),
        "global_stats": get_db_stats(global_db),
        "friction_backlog": find_friction_points(project_db, "project") + find_friction_points(global_db, "global")
    }
    
    # Deduplicate backlog by content
    seen = set()
    unique_backlog = []
    for item in report["friction_backlog"]:
        if item["content"] not in seen:
            unique_backlog.append(item)
            seen.add(item["content"])
    report["friction_backlog"] = unique_backlog
    
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
