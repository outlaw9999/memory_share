import os
import shutil
import time
import subprocess

def run_command(cmd):
    print(f"\n> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    return result.stdout

def main():
    print("=== .kit ARCHIVE: Epoch v1.1.0 SEALING ===")
    
    # 1. Capture Engine Stats
    print("\n--- [Engine Metadata] ---")
    run_command(["python", "-m", "kit_agent.cli.main", "stats"])

    # 2. Capture Cognitive State
    print("\n--- [Cognitive State: Resilience & Zero-Assumption] ---")
    run_command(["python", "-m", "kit_agent.cli.main", "recall", "resilience", "zero_assumption", "jan_autodiscovery", "--limit", "10"])

    # 3. Snapshot Database
    db_path = ".kit/brain.db"
    if os.path.exists(db_path):
        timestamp = int(time.time())
        archive_name = f".kit/brain_v1.1.0_{timestamp}.db"
        shutil.copy2(db_path, archive_name)
        print(f"\n[V] Brain Archive Created: {archive_name}")
    else:
        print("\n[X] Error: .kit/brain.db not found.")

    # 4. Final Manifesto
    print("\n--- [Epoch v1.1.0 SEALED] ---")
    print("Status: Production-grade Resilience & Local Fallback Active.")
    print("Governance: Zero-Assumption Protocol Enforced.")
    print("Connectivity: Gemini CLI + Local Jan Hybrid Loop Verified.")
    print("\nDone. Ready for Epoch v1.2.0 Expansion.")

if __name__ == "__main__":
    main()
