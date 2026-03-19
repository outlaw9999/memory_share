import sys
import os
import subprocess

def ingest_governance(file_path=None):
    """
    Upgraded Governance Ingester (v1.2.1-Robust)
    - Validates YAML/JSON integrity
    - Injects automated semantic tags
    - Fail-fast STDIN handling
    """
    print("[INGEST] Starting governance distillation (v1.2.1-Robust)...")
    
    try:
        import yaml
        use_yaml = True
    except ImportError:
        use_yaml = False
        print("[WARN] PyYAML not found. Proceeding with raw string ingestion.")

    content = ""
    try:
        if file_path and os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            print("[ERROR] No input source. Use: cat fact.yml | python scripts/governance_ingest.py")
            sys.exit(1)
            
        if not content.strip():
            print("[ERROR] Empty content.")
            sys.exit(1)

        # Validation & Tag Injection
        if use_yaml:
            try:
                data = yaml.safe_load(content)
                # Inject metadata if it's a list or dict
                if isinstance(data, dict):
                    data["_metadata"] = {"ingest_source": "governance_ingest_v1.2.1r", "status": "verified"}
                    content = yaml.dump(data)
                elif isinstance(data, list):
                    content = "---\n" + yaml.dump(data)
            except Exception as ye:
                print(f"[ERROR] YAML Validation failed: {str(ye)}")
                sys.exit(1)
            
        cmd = ["python", "kit.py", "learn", "--tag", "decision", "--no-render"]
        print(f"[INGEST] Sending {len(content)} bytes to SAMBrain...")
        
        result = subprocess.run(cmd, input=content, text=True, capture_output=True)
        
        if result.returncode == 0:
            print(f"[SUCCESS] {result.stdout.strip()}")
        else:
            print(f"[FAILURE] {result.stderr.strip()}")
            
    except Exception as e:
        print(f"[ERROR] Unhandled exception: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    ingest_governance(path)
