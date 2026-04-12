# scripts/invariant_checker.py
# v1.2.3 Invariant and Corruption Auditor

import os
import sqlite3
from pathlib import Path


def audit():
    print("--- v1.2.3 ARCHITECTURAL INVARIANT AUDIT ---")
    global_db = Path.home() / ".kit" / "global.db"

    if not global_db.exists():
        print(f"Error: Global DB {global_db} not found.")
        return

    conn = sqlite3.connect(str(global_db))
    conn.row_factory = sqlite3.Row

    # 1. Duplicate Structural Hashes
    dupes = conn.execute("""
        SELECT structural_hash, COUNT(*) as count 
        FROM observations 
        WHERE is_active = 1 AND structural_hash IS NOT NULL 
        GROUP BY structural_hash 
        HAVING count > 1
    """).fetchall()

    if dupes:
        print(f"❌ CRITICAL: {len(dupes)} Duplicate Structural Hashes found in active memory!")
        for d in dupes:
            print(f"  - Hash: {d['structural_hash']} (Count: {d['count']})")
    else:
        print("✅ No active duplicates found (Hash Idempotency active).")

    # 2. Entropy Anomalies (Potential Leaked Secrets)
    import math

    def calculate_entropy(text):
        if not text:
            return 0
        prob = [float(text.count(c)) / len(text) for c in dict.fromkeys(list(text))]
        return -sum([p * math.log(p) / math.log(2.0) for p in prob])

    records = conn.execute("SELECT id, content FROM observations WHERE is_active = 1").fetchall()
    anomalies = []
    for r in records:
        if calculate_entropy(r["content"]) > 4.5:  # Hard threshold for audit
            anomalies.append(r)

    if anomalies:
        print(f"⚠️  ANOMALY: {len(anomalies)} high-entropy records detected. Manual review recommended.")
        for a in anomalies:
            print(f"  - ID: {a['id']} | Entropy: {calculate_entropy(a['content']):.2f}")
    else:
        print("✅ No high-entropy anomalies detected in Global DB.")

    # 3. Decision Override Violations
    # (Future: check if a 'decision' tried to override an 'invariant')

    conn.close()
    print("\nAudit Complete.")


if __name__ == "__main__":
    audit()
