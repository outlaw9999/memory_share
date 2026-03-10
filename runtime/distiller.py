import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

class ContextDistiller:
    """
    Middleware for Cognitive Compression (Context Distillation).
    
    Responsibilities:
    1. Monitor Token footprint of the current session.
    2. Summarize 'Cold' transactions (older logs).
    3. Update the 'Hot State' to keep it lean (< 8000 tokens).
    """

    def __init__(self, workspace_root: Path, token_threshold: int = 8000):
        self.workspace_root = workspace_root
        self.token_threshold = token_threshold
        self.journal_path = workspace_root / ".antigravity" / "memory" / "journal.jsonl"
        self.summary_path = workspace_root / ".antigravity" / "memory" / "distilled_summary.json"

    def audit_footprint(self) -> int:
        """Estimate the token footprint of the current journal."""
        if not self.journal_path.exists():
            return 0
        
        # Simple estimation: 1 token approx 4 chars
        char_count = self.journal_path.stat().st_size
        return char_count // 4

    def distill(self, force: bool = False) -> bool:
        """
        Compress older journal entries into a cognitive summary.
        
        Workflow:
        1. Read all 'commit' entries.
        2. Identify the 'Cold' boundary (everything older than last 5 commits).
        3. Create a summary of cold changes (Files modded, Symbols touched).
        4. Truncate journal (optional/soft) and update distilled_summary.json.
        """
        if not force and self.audit_footprint() < self.token_threshold:
            return False

        # Phase 8: Mock distillation - in a real system, this would call an LLM to summarize
        # Here we perform structural distillation (Metadata-only)
        
        commits = []
        with open(self.journal_path, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                if record["type"] == "commit":
                    commits.append(record)

        if len(commits) < 10: # Don't distill too early
            return False

        cold_commits = commits[:-5]
        summary = {
            "distilled_at": time.time(),
            "cold_tx_count": len(cold_commits),
            "affected_files": list(set(c.get("file", "unknown") for c in cold_commits)),
            "summary_note": f"Phát hiện {len(cold_commits)} giao dịch cũ đã được nén vào tầng Layer 2 Core."
        }

        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        return True

    def get_injection_prompt(self) -> str:
        """Returns the summary to be injected into the LLM system prompt."""
        if not self.summary_path.exists():
            return ""
        
        with open(self.summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return f"\n[Distilled Memory]: Dự án đã thực hiện {data['cold_tx_count']} thay đổi trên các file: {', '.join(data['affected_files'])}. Các thay đổi này đã được nén để tiết kiệm token.\n"
