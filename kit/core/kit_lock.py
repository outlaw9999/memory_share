import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("kit.lock")


class LockError(Exception):
    pass


class ZombieHandleDetected(LockError):
    def __init__(self, handles: list[dict[str, Any]]) -> None:
        self.handles = handles
        super().__init__(f"Zombie handles detected: {[h.get('pid') for h in handles]}")


def get_db_files(db_path: Path) -> list[Path]:
    files = [db_path]
    if db_path.exists():
        wal = db_path.with_suffix(".db-wal")
        shm = db_path.with_suffix(".db-shm")
        if wal.exists():
            files.append(wal)
        if shm.exists():
            files.append(shm)
    return files


def truncate_wal(db_path: Path) -> bool:
    if not db_path.exists():
        return False

    import sqlite3
    from kit.core.memory_topology import MemoryTopologyFactory

    try:
        # Use topology to ensure consistent connection parameters
        topo = MemoryTopologyFactory.for_project(db_path.parent.parent)
        conn = topo.connect_path(db_path, readonly=False)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()
        logger.info(f"WAL truncated for {db_path.name}")
        return True
    except sqlite3.Error as e:
        logger.warning(f"Failed to truncate WAL: {e}")
        return False


def scan_zombie_handles(db_path: Path, timeout_seconds: float = 5.0) -> list[dict[str, Any]]:
    import psutil
    import time

    logger.info(f"scan_zombie_handles: Starting with {timeout_seconds}s timeout")
    zombies: list[dict[str, Any]] = []
    if not db_path.exists():
        logger.info("scan_zombie_handles: DB does not exist")
        return zombies

    db_str = str(db_path.resolve())
    start_time = time.time()

    try:
        logger.info("scan_zombie_handles: Iterating processes...")
        count = 0
        for proc in psutil.process_iter(["pid", "name", "open_files"]):
            if time.time() - start_time > timeout_seconds:
                logger.warning(f"scan_zombie_handles: Timeout after {timeout_seconds}s, checked {count} processes")
                break

            count += 1
            try:
                of = proc.info.get("open_files")
                if of is None:
                    continue

                for f in of:
                    fpath = getattr(f, "path", None)
                    if fpath and db_str.lower() in str(fpath).lower():
                        zombies.append(
                            {
                                "pid": proc.info["pid"],
                                "name": proc.info["name"],
                                "path": str(fpath),
                            }
                        )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        logger.info(
            f"scan_zombie_handles: Done. Checked {count} processes, found {len(zombies)} zombies"
        )
    except Exception as e:
        logger.warning(f"Handle scan failed: {e}")

    return zombies


def load_lock_state(root_path: Path) -> dict[str, Any]:
    state_file = root_path / ".kit" / "seal_state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sealed": False}


def save_lock_state(root_path: Path, state: dict[str, Any]) -> None:
    state_file = root_path / ".kit" / "seal_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def log_unseal_audit(root_path: Path, reason: str) -> None:
    from kit.core.memory_topology import MemoryTopologyFactory
    
    # v1.2.5-TITANIUM: Route audit traces to Global Trace Layer (L4)
    topo = MemoryTopologyFactory.for_project(root_path)
    audit_file = topo.resolve("global", "audit")
    
    audit_file.parent.mkdir(parents=True, exist_ok=True)

    import uuid
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "session_id": str(uuid.uuid4()),
        "action": "unseal",
        "reason": reason,
        "user": os.environ.get("USERNAME", "unknown"),
    }

    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def seal(
    db_path: Path,
    root_path: Path,
    force_evict: bool = False,
) -> dict[str, Any]:
    """Logical Seal: Blocks writes in-code without triggering OS-level read-only errors."""
    logger.info(f"Starting logical seal for {db_path}")
    state = load_lock_state(root_path)

    if state.get("sealed"):
        return {"status": "already_sealed", "sealed": True}

    # Step 1: Cleanup (Optional but recommended for consistency)
    logger.info("Truncating WAL for consistency...")
    truncate_wal(db_path)

    # Step 2: Handle Safety (Warn/Block if other processes are using it)
    logger.info("Scanning zombie handles...")
    zombies = scan_zombie_handles(db_path)
    
    if zombies and not force_evict:
        # v1.2.5: In a logical seal, we might still allow sealing if we only care about the state,
        # but to maintain 'forensic-grade' stability, we warn about concurrent handles.
        logger.warning(f"Concurrent handles detected during seal: {zombies}")

    if zombies and force_evict:
        import psutil
        for z in zombies:
            try:
                proc = psutil.Process(z["pid"])
                proc.terminate()
                logger.info(f"Terminated zombie PID {z['pid']}")
            except Exception as e:
                logger.warning(f"Failed to terminate {z['pid']}: {e}")

    # Step 3: Materialize Logical Seal
    logger.info("Saving logical seal state...")
    new_state = {
        "sealed": True,
        "db_path": str(db_path.resolve()),
        "timestamp": datetime.now(UTC).isoformat(),
        "seal_version": "1.2.5-LOGICAL",
    }
    save_lock_state(root_path, new_state)

    return {"status": "sealed", "sealed": True}


def unseal(db_path: Path, root_path: Path, reason: str) -> dict[str, Any]:
    """Reverts logical seal to allow learning."""
    state = load_lock_state(root_path)

    if not state.get("sealed"):
        return {"status": "not_sealed", "sealed": False}

    # Step 1: Mandatory Audit
    log_unseal_audit(root_path, reason)

    # Step 2: Clear State
    new_state = {
        "sealed": False, 
        "unseal_reason": reason,
        "timestamp": datetime.now(UTC).isoformat()
    }
    save_lock_state(root_path, new_state)

    logger.info(f"Logical seal removed: {reason}")
    return {"status": "unsealed", "sealed": False}


def is_sealed(root_path: Path) -> bool:
    """Authority Check for logical seal."""
    return load_lock_state(root_path).get("sealed", False)
