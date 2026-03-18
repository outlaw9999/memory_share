import os
import subprocess
import sys
import time
import sqlite3
import json
from pathlib import Path

# --- STRESS TEST CONFIG ---
CORE_DB = Path(".kit/brain.db")
REPORT_PATH = Path("tests/stress_test_report.md")

def run_cmd(cmd: list[str], env: dict | None = None) -> str:
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, 
        capture_output=True, 
        text=True, 
        encoding="utf-8", 
        env={**os.environ, **(env or {})}
    )
    return result.stdout + "\n" + result.stderr

def section(f, title):
    f.write(f"\n## {title}\n")
    print(f"\n>>> {title}")

def main():
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# [STRESS TEST] AMSB Resilience & Behavioral Stress Test\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 1. READINESS CHECK
        section(f, "1. READINESS CHECK")
        out = run_cmd(["python", "kit.py", "doctor", "--check-agents"])
        f.write("```\n" + out + "```\n")

        # 2. STORM TEST (503 CAPACITY)
        section(f, "2. STORM TEST (CAPACITY TRIGGER)")
        f.write("Triggering 5 continuous CAPACITY errors for Gemini...\n")
        
        # We run 5 tasks with Gemini simulated 503
        for i in range(5):
            print(f"Storm Attempt {i+1}/5...")
            out = run_cmd(
                ["python", "-m", "kit_agent.cli.main", "run", f"Stress Task {i}", "--provider", "gemini"],
                env={"GEMINI_SIMULATE_503": "1"}
            )
            if i == 0:
                f.write("First Failure Logs:\n```\n" + out + "```\n")
        
        # Check if Gemini is now DEGRADED
        section(f, "3. CIRCUIT BREAKER VERIFICATION")
        out = run_cmd(["python", "-m", "kit_agent.cli.main", "status"])
        f.write("System Status after Storm:\n```\n" + out + "```\n")
        
        # Verify Fallback (Should pick Local automatically)
        f.write("\nVerifying Automatic Fallback to Local...\n")
        out = run_cmd(["python", "-m", "kit_agent.cli.main", "run", "Fallback Check Task"])
        f.write("```\n" + out + "```\n")

        # 4. BEHAVIORAL AUDIT
        section(f, "4. BEHAVIORAL AUDIT (SCORING ENGINE v2)")
        f.write("Launching Behavioral Integrity Harness...\n")
        out = run_cmd(["pytest", "tests/test_behavioral_execution.py", "-v"])
        f.write("```\n" + out + "```\n")

        # 5. METRICS ANALYSIS
        section(f, "5. SQLITE METRICS ANALYSIS")
        if CORE_DB.exists():
            with sqlite3.connect(CORE_DB) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT name, data FROM agent_metrics").fetchall()
                f.write("| Provider | Healthy | Failures | Latency |\n")
                f.write("| :--- | :--- | :--- | :--- |\n")
                for row in rows:
                    data = json.loads(row["data"])
                    f.write(f"| {row['name']} | {data['healthy']} | {data['failures']} | {data['avg_latency']:.2f}s |\n")

        section(f, "6. CLI SYNC")
        run_cmd(["python", "kit.py", "stats"]) # Trigger render_context indirectly
        f.write("Manifests (.kit/context, AGENTS.md) synchronized.\n")

    print(f"\n[OK] Stress Test Complete. Report generated at {REPORT_PATH}")

if __name__ == "__main__":
    main()
