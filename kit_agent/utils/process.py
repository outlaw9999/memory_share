import subprocess
from typing import Optional, Tuple

def safe_run(cmd: list, input_text: Optional[str] = None, timeout: int = 15) -> Tuple[str, str, int]:
    """
    Run a command with timeout and input piping.
    Returns (stdout, stderr, returncode).
    Special returncode -1 for timeout.
    """
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False # Ensure safe execution
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "ERROR: TimeoutExpired", -1
    except Exception as e:
        return "", f"ERROR: {str(e)}", 1
