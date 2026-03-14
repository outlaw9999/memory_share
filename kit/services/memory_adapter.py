import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Any


class MemoryAdapter:
    """Adapter to query semantic memory from memory_share (Antigravity Brain v2)."""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.query_script = self.workspace_root / "brain" / "ops" / "query_layer3.py"

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search semantic memory using the layer3 query script."""
        if not self.query_script.exists():
            return [{"error": f"Memory query script not found: {self.query_script}"}]

        cmd = ["python", str(self.query_script), query, "--limit", str(limit), "--json"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return [{"error": f"Memory query failed: {result.stderr}"}]

            try:
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    return data
                return [{"data": data}]
            except json.JSONDecodeError:
                return [{"raw_output": result.stdout}]
        except Exception as e:
            return [{"error": f"Exception during memory query: {str(e)}"}]


if __name__ == "__main__":
    # Quick test
    adapter = MemoryAdapter(os.getcwd())
    print(adapter.search("AuthService race condition"))
