import os
import json
import time
import uuid
from pathlib import Path

class LockManager:
    """
    Antigravity AI-OS Memory Lock Manager
    Handles safe concurrency for Agents using Atomic OS-level File Locks and TTLs.
    """
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.antigravity_dir = self.workspace_root / ".antigravity"
        self.locks_dir = self.antigravity_dir / "memory" / "locks"
        
        # Ensure directories exist
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def _get_lock_path(self, target_resource: str) -> Path:
        """Converts a relative resource path to a lock file path."""
        safe_name = str(target_resource).replace("/", "_").replace("\\", "_")
        return self.locks_dir / f"{safe_name}.lock"

    def acquire(self, agent_id: str, target_resource: str, ttl: int = 300) -> str | None:
        """
        Attempts to acquire an atomic file lock.
        Returns the lock_id if successful, None if locked by another active agent.
        """
        lock_path = self._get_lock_path(target_resource)
        
        # 1. Check existing lock and detect stale locks (Deadlocks)
        if lock_path.exists():
            try:
                with open(lock_path, "r") as f:
                    lock_data = json.load(f)
                
                # If TTL expired, Governor force-releases the lock
                if time.time() - lock_data["started_at"] > lock_data["ttl"]:
                    print(f"[Governor GC] Stale lock detected on {target_resource} from {lock_data['agent']}. Forcing release.")
                    try:
                        lock_path.unlink()
                    except FileNotFoundError:
                        pass # Race condition safe
                else:
                    return None # 423 Locked
            except (json.JSONDecodeError, KeyError):
                # Corrupted lock file
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                
        # 2. Atomic File Creation
        lock_id = str(uuid.uuid4())
        lock_data = {
            "lock_id": lock_id,
            "agent": agent_id,
            "target": target_resource,
            "started_at": time.time(),
            "ttl": ttl
        }
        
        try:
            # os.O_EXCL ensures the file creation fails if it already exists -> true atomic concurrency
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as f:
                json.dump(lock_data, f)
                f.flush()
                os.fsync(f.fileno()) # Guarantee write to disk
            return lock_id
        except FileExistsError:
            # Lost the race condition to another agent just milliseconds ago
            return None
        except Exception as e:
            print(f"Failed to acquire lock: {e}")
            return None

    def release(self, agent_id: str, lock_id: str, target_resource: str) -> bool:
        """Releases a lock ONLY if owned by the correct agent and matching lock_id."""
        lock_path = self._get_lock_path(target_resource)
        if lock_path.exists():
            try:
                with open(lock_path, "r") as f:
                    lock_data = json.load(f)
                
                if lock_data.get("agent") == agent_id and lock_data.get("lock_id") == lock_id:
                    lock_path.unlink()
                    return True
            except Exception:
                pass
        return False
        
    def wait_and_acquire(self, agent_id: str, target_resource: str, ttl: int = 300, timeout: int = 30) -> str | None:
        """
        Blocks and retries acquiring the lock to prevent busy-spin.
        Waits up to `timeout` seconds before giving up.
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            lock_id = self.acquire(agent_id, target_resource, ttl)
            if lock_id:
                return lock_id
            
            # Backoff before retrying
            time.sleep(0.5)
            
        return None
