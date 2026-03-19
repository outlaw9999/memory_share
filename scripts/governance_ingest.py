import sys
import os
import subprocess
import yaml # Assuming PyYAML is available, fallback to json if needed

def ingest_governance(file_path=None):
    """
    Automates the ingestion of distilled memory facts into the .kit brain.
    Uses the v1.2.1 fail-fast patterns.
    """
    print("[INGEST] Starting governance distillation...")
    
    cmd = ["python", "kit.py", "learn", "--tag", "decision", "--no-render"]
    
    try:
        if file_path and os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            print("Error: No input provided via file or STDIN pipe.")
            sys.exit(1)
            
        if not content.strip():
            print("Error: Empty content.")
            sys.exit(1)
            
        print(f"[INGEST] Sending {len(content)} bytes to SAMBrain...")
        result = subprocess.run(cmd, input=content, text=True, capture_output=True)
        
        if result.returncode == 0:
            print(f"[SUCCESS] {result.stdout.strip()}")
        else:
            print(f"[FAILURE] {result.stderr.strip()}")
            
    except Exception as e:
        print(f"[ERROR] Ingestion failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    ingest_governance(path)
