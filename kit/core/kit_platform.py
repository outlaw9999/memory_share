import os
import subprocess
import sys
from collections.abc import Sequence

# Fail-Fast Doctrine Invariants (v1.2.3-ULTRA-GOLD)
# NO OPERATION MAY BLOCK > 1 SECOND WITHOUT EXPLICIT USER CONSENT
DEFAULT_TIMEOUT = 1.0
FAST_TIMEOUT = 0.2
LONG_TIMEOUT = 10.0  # Reserved for heavy operations like 'build' or 'ingest-all'
NETWORK_TIMEOUT = 0.5
GIT_TIMEOUT = 5.0  # Git operations need more time (index parsing, large repos)


def run_safe(
    cmd: Sequence[str],
    timeout: float = DEFAULT_TIMEOUT,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    shell: bool = False,
) -> subprocess.CompletedProcess[str]:
    """
    Standardized Subprocess Wrapper with Fail-Fast Enforcement.
    """
    try:
        return subprocess.run(cmd, timeout=timeout, capture_output=capture_output, text=text, check=check, shell=shell)
    except subprocess.TimeoutExpired as e:
        # Standardized timeout error message
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        print(f"\033[91m[FAIL-FAST] Operation timed out after {timeout}s: {cmd_str}\033[0m", file=sys.stderr)
        raise RuntimeError(f"Operation timed out ({timeout}s)") from e
    except Exception as e:
        raise RuntimeError(f"Subprocess failed: {e}") from e


def is_stdin_ready(timeout: float = FAST_TIMEOUT) -> bool:
    """
    Checks if STDIN has data waiting without blocking indefinitely.
    Cross-platform (POSIX via select, Windows via isatty + logic).
    """
    if not sys.stdin.isatty():
        if os.name == "nt":
            # Windows Pipe/Redirect: Minimal protection.
            # We check if there's any data available via peek/read if possible,
            # but usually we just want to avoid blocking if the pipe is open but empty.
            # For now, we use a fail-fast approach: expect data immediately or fail.
            return True  # In non-TTY, we usually have data if something was piped.
        try:
            import select

            return bool(select.select([sys.stdin], [], [], timeout)[0])
        except (ImportError, AttributeError, OSError):
            return True
    else:
        if os.name == "nt":
            # Windows TTY: Minimal wait or just return False if we can't check
            return False
        try:
            import select

            return bool(select.select([sys.stdin], [], [], timeout)[0])
        except (ImportError, AttributeError, OSError):
            return False


def read_stdin_fail_fast(timeout: float = FAST_TIMEOUT) -> str | None:
    """
    Reads from STDIN only if data is immediately available or appears within timeout.
    Uses threading on Windows to avoid blocking the main thread.
    """
    if os.name != "nt":
        if is_stdin_ready(timeout):
            try:
                return sys.stdin.read().strip()
            except EOFError:
                return None
        return None

    # Windows Threaded Fail-Fast
    import threading

    result: list[str] = []

    def _read() -> None:
        try:
            result.append(sys.stdin.read())
        except Exception:
            pass

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive() or not result:
        return None
    stripped: str = result[0].strip()
    return stripped
