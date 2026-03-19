import subprocess
import json
import sys
import os

def run_cmd(cmd, input_text=None):
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True if os.name == 'nt' else False
    )
    stdout, stderr = process.communicate(input=input_text)
    return stdout, stderr, process.returncode

def test_golden_path():
    print("--- [GOLDEN PATH TEST] ---")
    
    # 1. kit init
    print("1. Initializing .kit...")
    stdout, stderr, code = run_cmd(["python", "kit.py", "init"])
    if code != 0:
        print(f"FAILED: {stderr}")
        return

    # 2. kit learn (Invariant)
    print("2. Learning Invariant...")
    rule = "Auth must use JWT tokens only. No session cookies."
    stdout, stderr, code = run_cmd(["python", "kit.py", "learn", "--tag", "invariant", "--content", rule, "--uid", "auth_rule"])
    if code != 0:
        print(f"FAILED: {stderr}")
        return

    # 3. kit-agent ask (Evaluation)
    print("3. Asking Agent to Evaluate Violation...")
    task = "Can I use session cookies for the new login page?"
    # Use local for the golden path if gemini is not available
    stdout, stderr, code = run_cmd(["python", "-m", "kit_agent.cli.main", "ask", task, "--provider", "local"])
    
    print("\nAGENT OUTPUT:")
    print(stdout)
    
    if "BLOCK" in stdout:
        print("\nSUCCESS: Agent correctly blocked the invariant violation.")
    else:
        print("\nFAILED: Agent did not block the violation as expected.")

if __name__ == "__main__":
    test_golden_path()
