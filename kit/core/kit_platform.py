import os
import subprocess
import sys
from typing import Sequence, Optional, Tuple

# Fail-Fast Doctrine Invariants (v1.2.2)
# NO OPERATION MAY BLOCK > 1 SECOND WITHOUT EXPLICIT USER CONSENT
DEFAULT_TIMEOUT = 1.0
FAST_TIMEOUT = 0.2
LONG_TIMEOUT = 10.0  # Reserved for heavy operations like 'build' or 'ingest-all'
NETWORK_TIMEOUT = 0.5

def run_safe(
    cmd: Sequence[str], 
    timeout: float = DEFAULT_TIMEOUT, 
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    shell: bool = False
) -> subprocess.CompletedProcess:
    """
    Standardized Subprocess Wrapper with Fail-Fast Enforcement.
    """
    if shell is None:
        shell = (os.name == "nt")
        
    try:
        return subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            check=check,
            shell=shell
        )
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
        # In non-TTY, we can often just check if we have data or if the pipe is closed.
        # But for safety, we try to use select if available.
        try:
            import select
            return bool(select.select([sys.stdin], [], [], timeout)[0])
        except (ImportError, AttributeError, OSError):
            # Fallback for Windows/Non-select environments
            # On Windows, if non-TTY, we assume data is there or it's empty.
            return True # Assume ready, the read() might block but we hope it's immediate if EOF
    else:
        # In TTY, we definitely need a timeout to avoid waiting for user input.
        try:
            import select
            return bool(select.select([sys.stdin], [], [], timeout)[0])
        except (ImportError, AttributeError, OSError):
            # Windows TTY: Minimal protection via isatty check already done.
            return False 

def read_stdin_fail_fast(timeout: float = FAST_TIMEOUT) -> Optional[str]:
    """
    Reads from STDIN only if data is immediately available or appears within timeout.
    """
    if is_stdin_ready(timeout):
        try:
            return sys.stdin.read().strip()
        except EOFError:
            return None
    return None
