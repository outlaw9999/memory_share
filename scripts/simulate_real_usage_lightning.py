# scripts/simulate_real_usage_lightning.py
# v1.2.3 "Immortal Stability" Simulation (In-Process Version)
# High-entropy multi-project stress test (5000 ops)

import os
import sys
import random
import shutil
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(ROOT))

import kit.api as api

# --- CONFIG ---
TEMP_ROOT = ROOT / "tests" / "simulation_cluster"
PROJECTS = [TEMP_ROOT / f"proj_{i}" for i in range(5)]

# Payloads
SECRETS = ["password=abc123", "sk-live-5123", "AWS_SECRET=XYZ"]
NOISE = ["test", "hello world", "just a note", "random string " * 5]
LOCALS = ["Fixed bug in {} line {}", "Update component {}", "Refactor {} logic"]
GLOBALS = ["ARCH: All services MUST use {}", "Always follow protocol {}", "Standard invariant for {}"]

def simulate():
    print(f"--- STARTING 5000-OP LIGHTNING SIMULATION ---", flush=True)
    if TEMP_ROOT.exists():
        for i in range(5):
            try:
                shutil.rmtree(TEMP_ROOT)
                break
            except PermissionError:
                time.sleep(1)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    # Pre-init projects (via CLI to ensure schema_factory works)
    import subprocess
    PYTHON = sys.executable
    for p in PROJECTS:
        p.mkdir(parents=True, exist_ok=True)
        subprocess.run([PYTHON, "-m", "kit.cli.main", "init"], cwd=p, capture_output=True)
        print(f"  Project {p.name} initialized.", flush=True)

    # Import auto_route by path to avoid package issues
    import importlib.util
    spec = importlib.util.spec_from_file_location("auto_route", str(ROOT / "kit" / "cli" / "auto_route.py"))
    auto_route = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auto_route)

    ops = 5000
    start_time = time.time()
    stats = {"GLOBAL": 0, "LOCAL": 0, "DROP": 0, "BLOCK": 0, "SKIP": 0, "RECALL": 0}
    
    initial_cwd = Path.cwd()

    for i in range(ops):
        proj_path = random.choice(PROJECTS)
        os.chdir(proj_path)
        
        # Reset API kernel for each project to simulate context switch
        api._brain_instance = None
        api.init_kernel()
        
        mode = random.random()
        
        if mode < 0.1: # Secret (BLOCK)
            text = random.choice(SECRETS) + str(random.random())
        elif mode < 0.3: # Noise (DROP)
            text = random.choice(NOISE)
        elif mode < 0.6: # Local
            text = random.choice(LOCALS).format("file.py", i)
        elif mode < 0.8: # Global
            text = random.choice(GLOBALS).format("service_" + str(i % 10))
        else: # Recall
            api.recall(["service"], with_global=True)
            stats["RECALL"] += 1
            continue

        # In-process --auto logic
        try:
            res = auto_route.route_content(text)
            status = res.get("status")
            
            if status == "BLOCK":
                stats["BLOCK"] += 1
            elif status == "DROP":
                stats["DROP"] += 1
            elif status == "SKIP":
                stats["SKIP"] += 1
            else:
                route = res.get("route")
                h = res.get("hash")
                # Actual learning (using kit.api)
                api.learn(text, tag="decision" if route == "LOCAL" else "invariant", structural_hash=h)
                stats[route] += 1
        except Exception as e:
            import traceback
            print(f"  Error in op {i}: {e}")
            traceback.print_exc()

        if i % 500 == 0:
            print(f" Progress: {i}/{ops} | Status: {stats}", flush=True)

    os.chdir(initial_cwd)
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*50, flush=True)
    print(f"SIMULATION COMPLETE in {duration:.2f}s ({ops/duration:.2f} ops/sec)", flush=True)
    print(f"Final Outcome: {stats}", flush=True)
    
    # Final Integrity Check
    print("\n--- INTEGRITY AUDIT ---", flush=True)
    import sqlite3
    global_db = Path.home() / ".kit" / "global.db"
    conn = sqlite3.connect(str(global_db))
    dupes = conn.execute("SELECT structural_hash, COUNT(*) FROM observations WHERE is_active=1 AND structural_hash IS NOT NULL GROUP BY structural_hash HAVING COUNT(*) > 1").fetchall()
    if not dupes:
        print("✅ Idempotency: SECURE (0 duplicates in Global DB)", flush=True)
    else:
        print(f"❌ Duplicate Leak: {len(dupes)} entries found with same hash!", flush=True)
    conn.close()

if __name__ == "__main__":
    simulate()
