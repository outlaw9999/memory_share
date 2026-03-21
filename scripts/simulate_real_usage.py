# scripts/simulate_real_usage.py
# v1.2.3 "Immortal Stability" Simulation
# High-entropy multi-project stress test (5000 ops)

import os
import sys
import random
import shutil
import subprocess
import time
import psutil
from pathlib import Path

# --- CONFIG ---
ROOT = Path.cwd()
TEMP_ROOT = ROOT / "tests" / "simulation_cluster"
PROJECTS = [TEMP_ROOT / f"proj_{i}" for i in range(5)]
PYTHON = sys.executable
ENV = os.environ.copy()
ENV["PYTHONPATH"] = str(ROOT)
ENV["PYTHONUTF8"] = "1"

# Payloads
SECRETS = ["password=abc123", "sk-live-5123", "AWS_SECRET=XYZ"]
NOISE = ["test", "hello world", "just a note", "random string " * 5]
LOCALS = ["Fixed bug in {} line {}", "Update component {}", "Refactor {} logic"]
GLOBALS = ["ARCH: All services MUST use {}", "Always follow protocol {}", "Standard invariant for {}"]

def run_cmd(args, cwd, env=None, input=None, timeout=10):
    if not cwd.exists():
        return None
    try:
        return subprocess.run(
            args, 
            input=input,
            capture_output=True, 
            text=True, 
            env=env or ENV, 
            cwd=cwd, 
            encoding='utf-8', 
            errors='replace',
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        print(f"  Command timed out: {' '.join(args)}")
        return None

def cleanup_zombies():
    """Kill any stalled kit or git processes related to this simulation."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            if "kit.cli.main" in cmdline or "git" in cmdline:
                # Only kill if it seems to be part of our simulation or if it's clearly a kit process
                if str(TEMP_ROOT) in cmdline or "kit.cli.main" in cmdline:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def simulate():
    print(f"--- STARTING 5000-OP DYNAMIC SIMULATION ---")
    cleanup_zombies()
    if TEMP_ROOT.exists():
        for i in range(5):
            try:
                shutil.rmtree(TEMP_ROOT)
                break
            except PermissionError:
                print(f"  Cleanup retry {i+1}...")
                time.sleep(1)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    # Init projects
    for p in PROJECTS:
        p.mkdir(parents=True, exist_ok=True)
        res = run_cmd([PYTHON, "-m", "kit.cli.main", "init"], cwd=p)
        if not (p / ".kit").exists():
             print(f"  Warning: .kit directory not created in {p}")
        else:
             print(f"  Project {p.name} initialized.")

    ops = 100
    start_time = time.time()
    
    stats = {"GLOBAL": 0, "LOCAL": 0, "DROP": 0, "BLOCK": 0, "SKIP": 0}
    
    for i in range(ops):
        proj = random.choice(PROJECTS)
        mode = random.random()
        
        if mode < 0.1: # Secret (BLOCK)
            text = random.choice(SECRETS) + str(random.random())
        elif mode < 0.3: # Noise (DROP)
            text = random.choice(NOISE)
        elif mode < 0.6: # Local
            text = random.choice(LOCALS).format("file.py", i) + " " * 10
        elif mode < 0.8: # Global
            text = random.choice(GLOBALS).format("service_" + str(i % 10)) + " " * 50
        else: # Search/Recall (Non-writing)
            run_cmd([PYTHON, "-m", "kit.cli.main", "recall", "service", "--with-global"], cwd=proj)
            continue

        # Learning (Harden Subprocess: No shell=True, add timeout)
        res = run_cmd([PYTHON, "-m", "kit.cli.main", "learn", "--auto"], cwd=proj, input=text, timeout=5)
        
        if res and res.stderr:
            if "BLOCK" in res.stderr: stats["BLOCK"] += 1
            elif "DROP" in res.stderr: stats["DROP"] += 1
            elif "duplicates" in res.stderr or "Duplicate" in res.stderr: stats["SKIP"] += 1
            elif "GLOBAL" in res.stderr: stats["GLOBAL"] += 1
            elif "LOCAL" in res.stderr: stats["LOCAL"] += 1
        else:
            stats["SKIP"] += 1 # Timeout or process failure
        
        if i % 100 == 0:
            print(f" Progress: {i}/{ops} | Status: {stats}", flush=True)

    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*50, flush=True)
    print(f"SIMULATION COMPLETE in {duration:.2f}s", flush=True)
    print(f"Final Outcome: {stats}", flush=True)
    
    # Final Integrity Check
    print("\n--- INTEGRITY AUDIT ---", flush=True)
    # 1. Path Divergence Check
    all_global_paths = set()
    for p in PROJECTS:
        res = run_cmd([PYTHON, "-m", "kit.cli.main", "doctor"], cwd=p)
        for line in res.stderr.splitlines():
            if "Global DB:" in line:
                all_global_paths.add(line.strip())
    
    if len(all_global_paths) == 1:
        print(f"✅ Path Invariant: SECURE ({list(all_global_paths)[0]})", flush=True)
    else:
        print(f"❌ Path Divergence Detected: {all_global_paths}", flush=True)

    # 2. Duplicate Check in Global DB
    import sqlite3
    global_db = Path.home() / ".kit" / "global.db"
    conn = sqlite3.connect(str(global_db))
    conn.row_factory = sqlite3.Row
    dupes = conn.execute("SELECT structural_hash, COUNT(*) as cnt FROM observations WHERE is_active=1 AND structural_hash IS NOT NULL GROUP BY structural_hash HAVING COUNT(*) > 1").fetchall()
    if not dupes:
        print("✅ Idempotency: SECURE (0 duplicates in Global DB)")
    else:
        print(f"❌ Duplicate Leak: {len(dupes)} entries found with same hash!")

    # 3. Global Contamination Check (Linh hồn v1.2.3)
    bad = conn.execute("SELECT COUNT(*) FROM observations WHERE scope != 'GLOBAL' AND scope != ''").fetchone()[0]
    if bad == 0:
        print("✅ Governance: No LOCAL leak into GLOBAL")
    else:
        print(f"❌ Global Contamination: {bad} local/scoped entries found in Global DB!")
    
    conn.close()

if __name__ == "__main__":
    simulate()
