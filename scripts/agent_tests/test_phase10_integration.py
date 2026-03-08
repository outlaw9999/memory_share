import subprocess
import json
import os
import sys

def run_kit(command, args=None, timeout=5):
    cmd = [sys.executable, "kit.py", command]
    if args:
        cmd.extend(args)
    cmd.append("--json")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return {"error": result.stderr.strip()}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}

def test_fallback_detection():
    print("Testing Fallback Detection...")
    has_kit = os.path.exists("kit.py")
    print(f"kit.py exists: {has_kit}")
    if not has_kit:
        print("PASS: Environment detection correctly identifies absence of kit.py")
    else:
        print("INFO: kit.py found, proceeding with semantic tests")

def test_symbol_lookup():
    print("\nTesting Symbol Lookup (Deterministic)...")
    # Kernel is a class in runtime/kernel.py
    result = run_kit("symbol", ["Kernel"])
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return
    
    results_list = result.get("results", [])
    if not results_list:
        print(f"FAIL: Empty results list for 'Kernel'. Full output: {result}")
    else:
        item = results_list[0]
        print(f"PASS: Found symbol {item.get('name')} in {item.get('path')}")

def test_impact_analysis():
    print("\nTesting Impact Analysis (Incremental Audit)...")
    # Testing impact depth and limit
    result = run_kit("impact", ["Kernel", "--depth", "2", "--limit", "10"])
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return
    
    results_list = result.get("results", [])
    if not results_list:
        print(f"FAIL: Empty impact results. Full output: {result}")
    else:
        impact_data = results_list[0]
        affected = impact_data.get("affected", [])
        print(f"PASS: Impact analysis returned {len(affected)} nodes (metrics: {impact_data.get('metrics')})")

def test_empty_result_safety():
    print("\nTesting Empty Result Safety...")
    result = run_kit("symbol", ["NonExistentSymbol999"])
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return
        
    results_list = result.get("results", [])
    if results_list == []:
        print("PASS: Correctly returned empty list [] for unknown symbol")
    else:
        print(f"FAIL: Expected [], got {results_list}")

if __name__ == "__main__":
    test_fallback_detection()
    if os.path.exists("kit.py"):
        test_symbol_lookup()
        test_impact_analysis()
        test_empty_result_safety()
