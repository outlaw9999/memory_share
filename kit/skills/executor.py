import logging
import os
import subprocess
import sys
from typing import Any

logger = logging.getLogger("kit.skills.executor")

# v1.2.4-TITANIUM: Execution Depth Guard
MAX_DEPTH = 3
DEPTH_ENV_VAR = "KIT_SKILL_DEPTH"


def execute_skill(skill: dict[str, Any], dry_run: bool = False) -> bool:
    """
    Execute a procedural skill workflow with safety prompts and reification.
    """
    name = skill.get("name", "unknown")
    workflow = skill.get("workflow", [])

    # 0. Depth Guard
    current_depth = int(os.getenv(DEPTH_ENV_VAR, "0"))
    if current_depth >= MAX_DEPTH:
        logger.error(f"Skill execution depth limit reached ({MAX_DEPTH}). Aborting to prevent loop.")
        print(f"\n[kit] ERROR: Skill execution depth limit reached ({MAX_DEPTH}). Aborting.")
        return False

    print(f"\n[kit] Matched Skill: {name}")
    print("[kit] Proposed Workflow:")

    # 1. Preview & Reification
    commands = []
    venv_bin_dir = os.path.dirname(sys.executable)
    vantage_path = os.path.join(venv_bin_dir, "kit-vantage.exe") if sys.platform == "win32" else os.path.join(venv_bin_dir, "kit-vantage")

    for _i, step in enumerate(workflow, 1):
        raw_cmd = step.get("command", "")
        if not raw_cmd or not raw_cmd.strip():
            continue

        # v1.2.4-LOCK: Reification Guard (CRITICAL)
        reified_cmd = raw_cmd.strip()
        
        # If sys.executable (absolute path) is already in the command, we ABORT further reification
        # to prevent the python.exe.exe doubling bug.
        if sys.executable in reified_cmd:
            commands.append(reified_cmd)
            print(f"  {len(commands)}. {reified_cmd} (Verified: Reified)")
            continue

        # 1. Handle explicit placeholders FIRST (High Precision)
        if "{python}" in reified_cmd:
            reified_cmd = reified_cmd.replace("{python}", sys.executable)
        elif "{vantage}" in reified_cmd:
            reified_cmd = reified_cmd.replace("{vantage}", vantage_path)
        else:
            # 2. Keyword replacement with boundary checks
            import re
            # Reify 'python' only if it's NOT already part of a path
            reified_cmd = re.sub(r"(?<![\w./\\])\bpython\b(?!\.(exe|py))", lambda m: sys.executable, reified_cmd, count=1)
            reified_cmd = re.sub(r"(?<![\w./\\])\bkit-vantage\b(?!\.exe)", lambda m: vantage_path, reified_cmd, count=1)

        commands.append(reified_cmd)
        print(f"  {len(commands)}. {reified_cmd}")

    if not commands:
        print("  (No commands to execute)")
        return True

    if dry_run:
        print("\n[kit] Dry-run mode: skipping execution.")
        return True

    # 2. Confirmation (Mandatory for v0.1)
    print("\n" + "=" * 40)
    print("⚠️  SAFETY GATE: PROCEDURE VALIDATION")
    print("=" * 40)
    print("Review the workflow above. It will run in your environment.")
    try:
        ans = input("Proceed? [y/n]: ").strip().lower()
    except EOFError:
        # Fallback for non-interactive environments
        print("\n[kit] No interactive input detected. Skipping execution.")
        return False

    if ans != 'y':
        print("[kit] Execution cancelled.")
        return False

    # 3. Execution Phase
    # Set depth for subprocesses
    os.environ[DEPTH_ENV_VAR] = str(current_depth + 1)

    try:
        for cmd in commands:
            print(f"\n[kit] Running: {cmd}")
            # Use shell=True to support the full command string defined in YAML
            result = subprocess.run(cmd, shell=True)

            if result.returncode != 0:
                print(f"\n[kit] ERROR: Step failed with exit code {result.returncode}")
                return False
    finally:
        # Restore depth (though process usually exits)
        os.environ[DEPTH_ENV_VAR] = str(current_depth)

    print(f"\n[kit] Skill '{name}' executed successfully.")
    return True
