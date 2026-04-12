import json
import os
import subprocess
import time


def scan_repo_chunked():
    print("--- [CHUNKED COGNITIVE SCAN] ---")
    
    # 1. Get file list
    files = [f for f in os.listdir('.') if f.endswith('.py')]
    
    # 2. Map Phase: Scan each file for 'Cognitive Gaps'
    reports = []
    for f in files:
        print(f"Scanning {f}...")
        with open(f) as file:
            content = file.read()
        
        # Pipe file content to agent for ephemeral scan
        task = f"Identify architectural gaps or invariant violations in this file: {f}"
        cmd = ["python", "-m", "kit_agent.cli.main", "ask", task]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, shell=True if os.name == 'nt' else False)
        stdout, _ = process.communicate(input=content)
        reports.append(f"FILE: {f}\n{stdout}\n")

    # 3. Reduce Phase: Synthesize Final Report
    full_report = "\n".join(reports)
    print("\nSynthesizing Global Cognitive Report...")
    
    final_task = "Synthesize these individual file reports into one Global Cognitive Report for the repository."
    cmd = ["python", "-m", "kit_agent.cli.main", "ask", final_task]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, shell=True if os.name == 'nt' else False)
    final_report, _ = process.communicate(input=full_report)
    
    print("\n--- FINAL REPORT ---")
    print(final_report)


if __name__ == "__main__":
    scan_repo_chunked()
