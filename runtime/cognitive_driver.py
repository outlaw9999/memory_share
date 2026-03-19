import json
import os
import time
from pathlib import Path


class CognitiveMemoryDriver:
    """
    Antigravity AI-OS Memory Driver (Runtime Kernel)
    Handles: Multi-tier Locks, Journaling (WAL), Gatekeeper Validation, and Atomic Writes.
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.antigravity_dir = self.workspace_root / ".antigravity"
        self.memory_dir = self.antigravity_dir / "memory"
        self.locks_dir = self.memory_dir / "locks"
        self.journal_file = self.memory_dir / "journal.jsonl"

        # Ensure directories exist
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.journal_file.touch(exist_ok=True)

    def _get_lock_path(self, target_file: str) -> Path:
        """Converts a relative file path to a lock file path."""
        safe_name = str(target_file).replace("/", "_").replace("\\", "_")
        return self.locks_dir / f"{safe_name}.lock"

    def acquire_lock(self, agent_id: str, target_file: str, ttl_seconds: int = 300) -> bool:
        """Attempts to acquire an atomic file lock with TTL."""
        lock_path = self._get_lock_path(target_file)

        if lock_path.exists():
            try:
                with open(lock_path) as f:
                    lock_data = json.load(f)

                # Check for stale lock (Deadlock detection)
                if time.time() - lock_data["started_at"] > lock_data["ttl"]:
                    print(
                        f"[Governor] Detected stale lock on {target_file} from {lock_data['agent']}. Forcing release."
                    )
                    lock_path.unlink()  # Force unlock
                else:
                    return False  # 423 Locked
            except (json.JSONDecodeError, KeyError):
                lock_path.unlink()  # Corrupted lock file, delete it

        # Create atomic lock
        lock_data = {"agent": agent_id, "target": target_file, "started_at": time.time(), "ttl": ttl_seconds}

        # Use exclusive creation mode 'x' to prevent race condition during lock creation
        try:
            with open(lock_path, "x") as f:
                json.dump(lock_data, f)
            return True
        except FileExistsError:
            return False

    def release_lock(self, agent_id: str, target_file: str):
        """Releases a lock if owned by the agent."""
        lock_path = self._get_lock_path(target_file)
        if lock_path.exists():
            try:
                with open(lock_path) as f:
                    lock_data = json.load(f)
                if lock_data["agent"] == agent_id:
                    lock_path.unlink()
            except (json.JSONDecodeError, FileNotFoundError, OSError):
                pass  # Fail silently on release errors for robustness

    def append_journal(self, agent_id: str, action: str, target: str, status: str):
        """Write-Ahead Logging (WAL) for memory events."""
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "agent": agent_id,
            "action": action,
            "target": target,
            "status": status,
        }
        with open(self.journal_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def gatekeeper_validate(self, new_content: str) -> bool:
        """
        Invariant Check / Constitution Guard.
        """
        # Example hardcoded invariant
        if "JWT" in new_content.upper():
            print("[Gatekeeper] REJECTED: Architecture Invariant Violation (JWT used instead of OAuth).")
            return False
        return True

    def write_memory(self, agent_id: str, relative_path: str, new_content: str) -> bool:
        """
        The only safe write path for Agents.
        Workflow: Request Lock -> Gatekeeper -> Atomic Write via Temp -> Journal(Success) -> Release Lock
        """
        print(f"[{agent_id}] Requesting write to {relative_path}...")

        # 1. Acquire Lock (Domain or File)
        if not self.acquire_lock(agent_id, relative_path):
            print(f"[{agent_id}] ERROR 423: File is locked by another agent. Backing off.")
            self.append_journal(agent_id, "memory_write_attempt", relative_path, "423_locked")
            return False

        try:
            # 2. Journal Intention (Pending)
            self.append_journal(agent_id, "memory_write", relative_path, "pending")

            # 3. Gatekeeper Validation
            if not self.gatekeeper_validate(new_content):
                self.append_journal(agent_id, "memory_write", relative_path, "rejected_by_gatekeeper")
                return False

            # 4. Atomic Write to Markdown via Tmp File
            target_path = self.workspace_root / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            tmp_path = target_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Atomic replace
            os.replace(tmp_path, target_path)

            # 5. Journal Success
            self.append_journal(agent_id, "memory_write", relative_path, "success")
            print(f"[{agent_id}] Successfully wrote to {relative_path}.")

            return True

        finally:
            # 6. Always Release Lock
            self.release_lock(agent_id, relative_path)
