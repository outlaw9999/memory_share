import os
import subprocess
import sys

def run_command(cmd, env=None):
    print(f"\n> {' '.join(cmd)}")
    current_env = os.environ.copy()
    if env:
        current_env.update(env)
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=current_env)
    print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}", file=sys.stderr)
    return result

def main():
    print("=== kit-agent Gemini Resilience Smoke Test ===")
    
    # Pre-test: Reset metrics to have a clean state
    run_command(["python", "-m", "kit_agent.cli.main", "reset-metrics"])

    # 1. Test Gemini Fallback (Simulated 503)
    print("\n--- Phase 1: Gemini 503 Fallback ---")
    env_503 = {"GEMINI_SIMULATE_503": "1", "JAN_AUTO_DISCOVER": "1"}
    res = run_command(["python", "-m", "kit_agent.cli.main", "run", "Test resilience fallback", "--provider", "gemini"], env=env_503)
    
    if "fallback" in res.stdout.lower() or "local" in res.stdout.lower():
        print("SUCCESS: Gemini fallback triggered.")
    else:
        print("FAILURE: Gemini fallback not detected in output.")

    # 2. Test Cognitive Recall
    print("\n--- Phase 2: Cognitive Recall ---")
    # We'll recall some common tags mentioned in the prompt
    run_command(["python", "-m", "kit_agent.cli.main", "recall", "resilience", "zero_assumption", "--limit", "5"])

    # 3. Check Stats
    print("\n--- Phase 3: Engine Stats ---")
    run_command(["python", "-m", "kit_agent.cli.main", "stats"])

    print("\n=== Smoke Test Complete ===")

if __name__ == "__main__":
    main()
