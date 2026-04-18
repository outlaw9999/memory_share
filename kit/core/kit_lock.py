import json
import logging
import os
import platform
import subprocess
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

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
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
            if count % 100 == 0:
                logger.info(f"scan_zombie_handles: Checked {count} processes")

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
            except psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess:
                continue
        logger.info(
            f"scan_zombie_handles: Done. Checked {count} processes, found {len(zombies)} zombies in {time.time() - start_time:.1f}s"
        )
    except Exception as e:
        logger.warning(f"Handle scan failed: {e}")

    return zombies

    db_str = str(db_path.resolve())
    logger.info(f"scan_zombie_handles: Looking for {db_str}")

    try:
        logger.info("scan_zombie_handles: Iterating processes...")
        count = 0
        for proc in psutil.process_iter(["pid", "name", "open_files"]):
            count += 1
            if count % 50 == 0:
                logger.info(f"scan_zombie_handles: Checked {count} processes")

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
            except psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess:
                continue
        logger.info(f"scan_zombie_handles: Done. Checked {count} processes, found {len(zombies)} zombies")
    except Exception as e:
        logger.warning(f"Handle scan failed: {e}")

    return zombies

    db_str = str(db_path.resolve())

    try:
        for proc in psutil.process_iter(["pid", "name", "open_files"]):
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
            except psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess:
                continue
    except Exception as e:
        logger.warning(f"Handle scan failed: {e}")

    return zombies


def apply_os_lock(db_path: Path) -> bool:
    if not db_path.exists():
        return False

    files = get_db_files(db_path)
    success = True

    if platform.system() == "Windows":
        for f in files:
            try:
                subprocess.run(
                    ["attrib", "+R", str(f)],
                    check=True,
                    capture_output=True,
                    timeout=5,
                )
                logger.info(f"OS lock applied to {f.name}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to lock {f.name}: {e}")
                success = False
            except Exception as e:
                logger.error(f"Unexpected error locking {f.name}: {e}")
                success = False
    else:
        logger.warning("OS lock not implemented for non-Windows platforms")
        success = False

    return success


def remove_os_lock(db_path: Path) -> bool:
    if not db_path.exists():
        return False

    files = get_db_files(db_path)
    success = True

    if platform.system() == "Windows":
        for f in files:
            try:
                subprocess.run(
                    ["attrib", "-R", str(f)],
                    check=True,
                    capture_output=True,
                    timeout=5,
                )
                logger.info(f"OS lock removed from {f.name}")
            except Exception as e:
                logger.warning(f"Failed to remove lock from {f.name}: {e}")
                success = False
    else:
        success = False

    return success


def verify_lock_effectiveness(db_path: Path) -> bool:
    if not db_path.exists():
        return False

    try:
        with open(db_path, "ab") as _:
            pass
        logger.error("OS lock verification FAILED: file is writable")
        return False
    except PermissionError:
        logger.info("OS lock verification PASSED: file is not writable")
        return True
    except Exception as e:
        logger.warning(f"Lock verification error: {e}")
        return False


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
    
    # v1.2.4-TITANIUM: Route audit traces to Global Trace Layer (L4)
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
    logger.info(f"Starting seal process for {db_path}")
    state = load_lock_state(root_path)
    logger.info(f"Loaded state: {state}")

    if state.get("sealed"):
        return {"status": "already_sealed", "sealed": True}

    logger.info("Truncating WAL...")
    truncate_wal(db_path)

    logger.info("Scanning zombie handles...")
    zombies = scan_zombie_handles(db_path)
    logger.info(f"Found {len(zombies)} zombies")

    if zombies and not force_evict:
        raise ZombieHandleDetected(zombies)

    if zombies and force_evict:
        for z in zombies:
            try:
                proc = __import__("psutil").Process(z["pid"])
                proc.terminate()
                logger.info(f"Terminated zombie PID {z['pid']}")
            except Exception as e:
                logger.warning(f"Failed to terminate {z['pid']}: {e}")

    logger.info("Applying OS lock...")
    if not apply_os_lock(db_path):
        raise LockError("Failed to apply OS lock")

    logger.info("Verifying lock effectiveness...")
    if not verify_lock_effectiveness(db_path):
        remove_os_lock(db_path)
        raise LockError("Lock verification failed")

    logger.info("Saving lock state...")
    new_state = {
        "sealed": True,
        "db_path": str(db_path),
        "timestamp": str(Path(__file__).stat().st_mtime),
    }
    save_lock_state(root_path, new_state)

    return {"status": "sealed", "sealed": True}


def unseal(db_path: Path, root_path: Path, reason: str) -> dict[str, Any]:
    state = load_lock_state(root_path)

    if not state.get("sealed"):
        return {"status": "not_sealed", "sealed": False}

    log_unseal_audit(root_path, reason)

    remove_os_lock(db_path)

    new_state = {"sealed": False, "unseal_reason": reason}
    save_lock_state(root_path, new_state)

    return {"status": "unsealed", "sealed": False}


def is_sealed(root_path: Path) -> bool:
    return load_lock_state(root_path).get("sealed", False)
