import sys
import os
import subprocess
from pathlib import Path
import tempfile
import json
import shutil

# Add project root to sys.path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

def run_cross_lang_audit():
    print("Starting Cross-Language Graph Audit (v1.2.4-RC1)")
    
    # 1. Prepare temp environment
    tmp_dir_obj = tempfile.TemporaryDirectory()
    tmp_path = Path(tmp_dir_obj.name)
    print(f"  Using temp workspace: {tmp_path}")
    
    # ISOLATE BEFORE ANY KIT IMPORTS
    test_env = os.environ.copy()
    test_env["KIT_GLOBAL_HOME"] = str(tmp_path / ".kit_global")
    os.environ["KIT_GLOBAL_HOME"] = test_env["KIT_GLOBAL_HOME"]
    (tmp_path / ".kit_global").mkdir()
    (tmp_path / ".kit-root").touch()

    # Now we can import kit.api safely
    import kit.api as api
    from kit.core.kit_vantage import VANTAGE_BIN
        
    # 1. Create mixed-language repo
    (tmp_path / "src").mkdir()
    
    # Python
    with open(tmp_path / "src" / "app.py", "w") as f:
        f.write("def run_logic():\n    print('Hello')\n")
        
    # JS (React style)
    with open(tmp_path / "src" / "Component.jsx", "w") as f:
        f.write("export function Header() {\n  return <h1>Header</h1>;\n}\n")
        
    # Rust
    with open(tmp_path / "src" / "lib.rs", "w") as f:
        f.write("pub fn core_logic() {\n    println!(\"Rust core\");\n}\n")
        
    # 2. Initialize Kit with isolation
    os.chdir(tmp_path)
    (tmp_path / ".kit-root").touch() # Force this to be project root
    
    print(f"  Initializing Kit in {tmp_path}...")
    subprocess.run([sys.executable, "-m", "kit.cli.main", "init"], check=True, env=test_env)
    
    # 3. Extract and Ingest Edges
    print("  Extracting edges via Vantage...")
    edge_file = tmp_path / "edges.jsonl"
    with open(edge_file, "w") as f:
        subprocess.run([str(VANTAGE_BIN), "extract-edges", "."], stdout=f, check=True, env=test_env)
        
    print("  Ingesting into Kit...")
    # v1.2.4: In RC1, we need to ensure the DB exists before ingestion
    # We'll use the CLI to trigger ingestion in the test env
    brain_root = tmp_path / ".kit"
    stream_path = brain_root / "local" / ".vantage" / "vantage_stream.jsonl"
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(edge_file, stream_path)
    
    subprocess.run([sys.executable, "-m", "kit.cli.main", "ingest"], check=True, env=test_env)
    
    # 4. Verify Graph Correctness
    print("  Verifying graph structure...")
    # We need to use api.init_kernel in the test environment to check results
    os.environ["KIT_GLOBAL_HOME"] = test_env["KIT_GLOBAL_HOME"]
    api.init_kernel(db_path=None, mode="auto")
    brain = api.get_brain()
    with brain.get_connection(readonly=True) as conn:
        rows = conn.execute("SELECT source, target, relation FROM structure_edges").fetchall()
        print(f"  Found {len(rows)} structural edges.")
        
        # Basic validation: check if symbols from all languages are present
        symbols = set()
        for r in rows:
            symbols.add(r[0])
            symbols.add(r[1])
        
        print(f"  Symbols: {symbols}")
        
        # We expect to see 'run_logic', 'Header', 'core_logic' or similar identifiers
        found_py = any("run_logic" in s for s in symbols)
        found_js = any("Header" in s for s in symbols)
        found_rs = any("core_logic" in s for s in symbols)
        
        if found_py and found_js and found_rs:
            print("[OK] Cross-language graph alignment verified.")
        else:
            print(f"[FAIL] Missing language representation. Py:{found_py}, JS:{found_js}, Rs:{found_rs}")
            sys.exit(1)

if __name__ == "__main__":
    run_cross_lang_audit()
