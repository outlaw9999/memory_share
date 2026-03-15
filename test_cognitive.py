import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.append(os.getcwd())

from kit import api

def cognitive_layers_test():
    db_path = Path("cognitive.db")
    if db_path.exists():
        db_path.unlink()
        
    print("🧠 Starting Cognitive Layers Verification...")
    api.init_kernel(db_path)
    
    # 1. Setup Layers
    print("📥 Ingesting mixed-layer knowledge...")
    
    # Procedural: An old instruction
    api.learn("coding_style", "procedural", "Always use 4 spaces for indentation", layer="procedural")
    
    # Semantic: A definition from a month ago
    api.learn("jwt", "semantic", "JWT stands for JSON Web Token", layer="semantic")
    
    # Episodic: A recent event
    api.learn("deploy", "episodic", "Deployed version 1.1.1 successfully", layer="episodic")
    
    # Working: A very fresh task
    api.learn("debug", "task", "Investigating Redis timeout", layer="working")
    
    # Simulate time passing via manual DB update
    with api.get_brain()._get_connection() as conn:
        # Instruction is 1 year old
        conn.execute("UPDATE facts SET created_at = julianday('now', '-365 days') WHERE content LIKE '%spaces%'")
        # Definition is 60 days old
        conn.execute("UPDATE facts SET created_at = julianday('now', '-60 days') WHERE content LIKE '%JSON%'")
        # Working task is 3 hours old
        conn.execute("UPDATE facts SET created_at = julianday('now', '-0.125 days') WHERE content LIKE '%Redis%'")
        
    # 2. Verify Ranking Priority
    print("\n🧐 Checking ranking priority...")
    uids = ["coding_style", "jwt", "deploy", "debug"]
    results = api.recall(uids, limit=10)
    
    for i, r in enumerate(results):
        print(f"  {i+1}. [{r.entity_uid}] {r.content}")
        
    # Procedural x10 should be top, Working x20 (even with small decay) should be high
    if "Redis" in results[0].content or "spaces" in results[0].content:
        print("\n✅ RANKING VERIFIED: Hierarchical layers respected.")
    else:
        print("\n❌ RANKING FAIL: Priority logic mismatch.")

if __name__ == "__main__":
    cognitive_layers_test()
