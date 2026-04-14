import subprocess

from kit.core.kit_platform import DEFAULT_TIMEOUT


def safe_run(cmd: list, input_text: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> tuple[str, str, int]:
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
            shell=False,  # Ensure safe execution
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "ERROR: TimeoutExpired", -1
    except Exception as e:
        return "", f"ERROR: {str(e)}", 1
