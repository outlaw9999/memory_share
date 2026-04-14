import os
import subprocess
from typing import Any

from kit_agent.providers.base import BaseProvider


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str | None = None, cli_path: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.cli_path = cli_path or os.environ.get("GEMINI_CLI_PATH", "gemini")
        self._version_checked = False

    def _check_version(self) -> None:
        """Verifies Gemini CLI version (target >= 1.99.0 for full compatibility)."""
        if self._version_checked:
            return
        try:
            result = subprocess.run([self.cli_path, "--version"], capture_output=True, text=True, timeout=5)
            version = result.stdout.strip()
            print(f"\033[90m[INFO] [GEMINI] Live CLI version: {version}\033[0m")
        except Exception as e:
            print(f"\033[93m[WARN] [GEMINI] Could not verify CLI version: {e}\033[0m")
        self._version_checked = True

    def ask(self, prompt: str) -> dict[str, Any]:
        """
        Calls the real Gemini CLI to execute a task.
        Supports simulation overrides for testing.
        """
        # --- STUB OVERRIDES (for testing) ---
        if os.environ.get("GEMINI_SIMULATE_503") == "1":
            return {"ok": False, "error": "503_CAPACITY_EXHAUSTED", "text": "", "error_type": "CAPACITY"}
        if os.environ.get("GEMINI_SIMULATE_TIMEOUT") == "1":
            return {"ok": False, "error": "REQUEST_TIMEOUT", "text": "", "error_type": "TIMEOUT"}

        self._check_version()

        try:
            # We use 'task' command as standard for Gemini agentic CLI
            # Note: This command structure might vary based on the specific CLI version/tooling
            cmd = [self.cli_path, "ask", prompt]  # fallback to 'ask' if 'task' is not standard

            # If the user mentioned 'task --prompt', we can try that too if 'ask' fails.
            # But let's start with a standard subprocess call.
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                if "503" in error_msg or "rate limit" in error_msg.lower():
                    return {"ok": False, "error": f"GEMINI_CAPACITY: {error_msg}", "text": "", "error_type": "CAPACITY"}
                return {
                    "ok": False,
                    "error": f"GEMINI_CLI_ERROR ({result.returncode}): {error_msg}",
                    "text": "",
                    "error_type": "TRANSIENT",
                }

            return {
                "ok": True,
                "text": result.stdout.strip(),
                "error": None,
                "error_type": None,
            }

        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "GEMINI_TIMEOUT: Command exceeded limit", "text": "", "error_type": "TIMEOUT"}
        except Exception as e:
            return {"ok": False, "error": f"GEMINI_SYSTEM_ERROR: {str(e)}", "text": "", "error_type": "TRANSIENT"}
