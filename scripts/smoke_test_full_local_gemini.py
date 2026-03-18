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
    print("=== kit-agent Full-Chain Local + Gemini Smoke Test ===")
    
    # Pre-test: Reset metrics
    run_command(["python", "-m", "kit_agent.cli.main", "reset-metrics"])

    # 1. Test Gemini (Healthy Stub)
    print("\n--- Phase 1: Gemini (Healthy) ---")
    # For Gemini stub to be "healthy", we just need an API key non-empty (it's a stub anyway)
    env_gemini = {"GEMINI_API_KEY": "stub-key"}
    run_command(["python", "-m", "kit_agent.cli.main", "run", "Test Gemini Healthy", "--provider", "gemini"], env=env_gemini)

    # 2. Test Local Jan (Explicit)
    print("\n--- Phase 2: Local Jan (Explicit) ---")
    # We enable auto-discovery to test it
    env_local = {"JAN_AUTO_DISCOVER": "1", "JAN_MODEL_ID": "jan-v3-4b"}
    run_command(["python", "-m", "kit_agent.cli.main", "run", "Test Local Jan", "--provider", "local"], env=env_local)

    # 3. Test Gemini Fallback to Local
    print("\n--- Phase 3: Gemini Fallback ---")
    env_fallback = {"GEMINI_SIMULATE_503": "1", "JAN_AUTO_DISCOVER": "1"}
    run_command(["python", "-m", "kit_agent.cli.main", "run", "Test Fallback Chain", "--provider", "gemini"], env=env_fallback)

    # 4. Cognitive Recall across multiple tags
    print("\n--- Phase 4: Full Cognitive Recall ---")
    run_command(["python", "-m", "kit_agent.cli.main", "recall", "resilience", "zero_assumption", "jan_autodiscovery", "doctrine", "--limit", "10"])

    # 5. Check Engine Stats & Verification
    print("\n--- Phase 5: Verification & End-to-End Metrics ---")
    run_command(["python", "-m", "kit_agent.cli.main", "stats"])

    print("\n=== Full-Chain Smoke Test Complete ===")

if __name__ == "__main__":
    main()
