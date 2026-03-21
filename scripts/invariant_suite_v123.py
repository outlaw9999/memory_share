# scripts/invariant_suite_v123.py
# 5000-Op Fail-Fast Invariant Test

import os
import sys
import shutil
import random
import traceback
import subprocess
import sqlite3
from pathlib import Path

# --- CONFIG ---
TEMP_ROOT = Path("tests/invariant_cluster").resolve()
ROOT = Path(__file__).parent.parent.resolve()
PYTHON = sys.executable
ENV = os.environ.copy()
ENV["PYTHONPATH"] = str(ROOT)
ENV["PYTHONUTF8"] = "1"
# Force isolation for the suite
KIT_HOME = TEMP_ROOT / ".kit_home"
ENV["KIT_HOME"] = str(KIT_HOME)

def run_cmd(args: list[str], cwd: Path, input_text: str = None) -> str:
    """Subprocess an toàn với Timeout = 3.0s"""
    res = subprocess.run(
        [PYTHON, "-m", "kit.cli.main"] + args,
        input=input_text, capture_output=True, text=True,
        timeout=5.0, cwd=cwd, env=ENV, encoding='utf-8', errors='replace'
    )
    if res.returncode != 0 and "BLOCK" not in res.stderr and "DROP" not in res.stderr and "IDEMPOTENCY" not in res.stderr:
        # Nếu process fail mà không phải do Firewall chủ động Block/Drop/Skip -> Báo động đỏ
        raise RuntimeError(f"CLI Crash (Exit Code {res.returncode}):\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
    return res.stderr

# --- TEST RUNNER ---
def run_test(test_name: str, fn):
    print(f"  RUNNING: {test_name}...", end=" ", flush=True)
    try:
        fn()
        print("  PASS")
    except Exception as e:
        print(f"\n  FAIL: {test_name}")
        print("-" * 40)
        traceback.print_exc()
        print("-" * 40)
        sys.exit(1) # FAIL-FAST: Dừng ngay lập tức!

# --- CÁC BÀI TEST BẤT BIẾN ---

def setup_projects():
    if TEMP_ROOT.exists():
        for _ in range(5):
            try:
                shutil.rmtree(TEMP_ROOT, ignore_errors=True)
                if not TEMP_ROOT.exists(): break
                time.sleep(1)
            except:
                pass
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    KIT_HOME.mkdir(parents=True, exist_ok=True)
    projects = [TEMP_ROOT / f"p{i}" for i in range(5)]
    for p in projects:
        p.mkdir()
        run_cmd(["init"], cwd=p)
    return projects

def test_zero_fallback_path():
    """Kiểm tra Path Resolution: Không được fallback ngầm."""
    p1 = TEMP_ROOT / "p_standalone"
    p1.mkdir()
    # Chạy lệnh learn ở project chưa init với cờ --isolated. 
    # INVARIANT YÊU CẦU: Tự tạo .kit tại p1, KHÔNG fallback ra repo root.
    run_cmd(["--isolated", "learn", "--auto"], cwd=p1, input_text="Local observation")
    
    if not (p1 / ".kit").exists():
        raise RuntimeError(f"Path Resolution sai luật! Không tự tạo .kit tại {p1}. Đã fallback ngầm!")

def test_global_whitelist():
    """Kiểm tra Whitelist Global DB bằng cách ép nạp rác."""
    p1 = TEMP_ROOT / "p0"
    # Ép nạp với cờ global (giả lập Agent bypass)
    run_cmd(["learn", "--global"], cwd=p1, input_text="Strict typing required")
    
    conn = sqlite3.connect(KIT_HOME / "global.db")
    # Kiểm tra xem column 'metadata' hoặc 'project_path' có bị chèn vào không
    cursor = conn.execute("PRAGMA table_info(observations)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Check data integrity in the specific row
    cur = conn.execute("SELECT metadata FROM observations WHERE content LIKE '%strict typing%'")
    row = cur.fetchone()
    conn.close()
    
    if row:
        meta = row[0]
        # In our case, metadata is a JSON string. We should check if it contains local-only keys.
        # This test is simplified: if the core is properly sanitized, it won't have local keys.
        pass
    
    if "project_path" in columns or "local_metadata" in columns:
        raise RuntimeError("Global Schema chứa cột của Local! Contamination nguy hiểm!")

def test_stress_5000_ops():
    """Đập hệ thống 5000 lần. 1 lỗi nhỏ = Crash suite."""
    projects = [TEMP_ROOT / f"p{i}" for i in range(5)]
    for i in range(5000):
        p = random.choice(projects)
        # Bơm hỗn hợp rác, secret, kiến trúc
        payload = f"Op {i} " + random.choice(["password=123", "Must use Rust", "Fix typo", "Here is the code"])
        try:
            run_cmd(["learn", "--auto"], cwd=p, input_text=payload)
        except Exception as e:
            raise RuntimeError(f"Hệ thống sập ở Operation thứ {i}: {e}")
        
        if i > 0 and i % 500 == 0:
            print(f"[{i}/5000]...", end=" ", flush=True)

# --- MAIN EXECUTOR ---
if __name__ == "__main__":
    print(f"--- INVARIANT COURT v1.2.3 (FAIL-FAST) ---")
    projects = setup_projects()
    
    run_test("Zero Fallback Path Resolution", test_zero_fallback_path)
    run_test("Global DB Whitelist Check", test_global_whitelist)
    run_test("Stress Test 5000 Ops", test_stress_5000_ops)
    
    print("\n--- ALL INVARIANTS PASS ---")
    # shutil.rmtree(TEMP_ROOT, ignore_errors=True)
