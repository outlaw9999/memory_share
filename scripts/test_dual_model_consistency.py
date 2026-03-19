import json
import os
import subprocess


def run_agent(task, provider):
    cmd = ["python", "-m", "kit_agent.cli.main", "ask", task, "--provider", provider]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True if os.name == 'nt' else False
    )
    stdout, _ = process.communicate()
    return stdout

def test_consistency():
    print("--- [DUAL-MODEL CONSISTENCY TEST] ---")
    task = "Can I use session cookies for login?"
    
    print("Running task with Gemini...")
    gemini_out = run_agent(task, "gemini")
    
    print("Running task with Local Jan...")
    jan_out = run_agent(task, "local")
    
    print("\nGEMINI DECISION:")
    print(gemini_out)
    
    print("\nJAN DECISION:")
    print(jan_out)

    gemini_block = "BLOCK" in gemini_out
    jan_block = "BLOCK" in jan_out

    if gemini_block == jan_block:
        print("\nSUCCESS: Decision alignment verified.")
    else:
        print("\nFAILED: Decision drift detected between models.")

if __name__ == "__main__":
    test_consistency()
