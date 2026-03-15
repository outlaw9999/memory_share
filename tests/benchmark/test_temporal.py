import sys
import os
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.append(os.getcwd())

from kit import api

def temporal_test():
    db_path = Path("temporal.db")
    if db_path.exists():
        db_path.unlink()
        
    print("⏳ Starting Temporal Audit Test...")
    api.init_kernel(db_path)
    
    # 1. Timeline Setup
    print("📅 Stage 0: T0 - Learning Initial Truth...")
    # We use manual julianday manipulation for testing speed
    api.learn("redis", "infra", "Redis is a fast in-memory store")
    api.learn("auth", "infra", "Auth uses Redis (T0)")
    api.link_entities("auth", "redis", "USES")
    
    with api.get_brain()._get_connection() as conn:
        conn.execute("UPDATE facts SET created_at = julianday('now', '-1 day')")
        conn.execute("UPDATE relations SET created_at = julianday('now', '-1 day')")
        t0 = (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")

    print(f"  - T0 established at: {t0} (Simulated yesterday)")

    # 2. Update Knowledge
    print("\n📅 Stage 1: T1 - Superseding Knowledge...")
    # Get ID of first fact belonging to 'auth'
    with api.get_brain()._get_connection() as conn:
        fid = conn.execute("""
            SELECT f.id FROM facts f 
            JOIN entities e ON f.entity_id = e.id 
            WHERE f.content LIKE '%Redis%' AND e.uid = 'auth'
        """).fetchone()["id"]
    
    api.learn("kafka", "infra", "Kafka is a distributed streaming platform")
    api.learn("auth", "infra", "Auth uses Kafka (T1)", replaces_id=fid)
    api.link_entities("auth", "kafka", "USES", supersede=True)
    
    # 3. Verification: Today
    print("\n🧐 Verifying 'Today' (Should see Kafka):")
    res_now = api.recall(["auth"])
    for r in res_now:
        print(f"  - [{r.entity_uid}] {r.content}")
    
    # 4. Verification: Yesterday (Snapshot T0)
    print(f"\n🧐 Verifying Snapshot at T0: {t0} (Should see Redis):")
    res_t0 = api.recall(["auth"], at=t0)
    for r in res_t0:
        print(f"  - [{r.entity_uid}] {r.content}")

    # Success criteria
    redis_in_t0 = any("Redis" in r.content for r in res_t0)
    kafka_in_now = any("Kafka" in r.content for r in res_now)
    
    if redis_in_t0 and kafka_in_now:
        print("\n✅ TEMPORAL TRUTH VERIFIED: Snapshot logic works perfectly.")
    else:
        print("\n❌ TEMPORAL LOGIC FAIL: Data leakage detected between timelines.")

if __name__ == "__main__":
    temporal_test()
