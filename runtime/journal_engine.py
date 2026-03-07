import json
import os
import uuid
import time
from pathlib import Path
from typing import Callable, Dict, Any

class JournalEngine:
    """
    Write-Ahead Log (WAL) Journal Engine for Antigravity Memory Kernel.
    Records semantic intents (AST operations) before they are applied.
    """
    def __init__(self, workspace_root: str):
        self.journal_path = Path(workspace_root) / ".antigravity" / "memory" / "journal.jsonl"
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal_path.touch(exist_ok=True)
        
    def log_intent(self, agent_id: str, target_file: str, operation: str, node_data: Dict[str, Any], old_hash: str) -> str:
        """
        Ghi lại ý định thay đổi (Semantic Intent) trước khi thực hiện.
        Yêu cầu `old_hash` để đảm bảo Optimistic Concurrency Control.
        """
        txn_id = str(uuid.uuid4())
        record = {
            "txn_id": txn_id,
            "ts": time.time(),
            "agent": agent_id,
            "target": target_file,
            "op": operation,
            "node": node_data,
            "old_hash": old_hash,
            "status": "pending"
        }
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return txn_id

    def commit(self, txn_id: str, new_hash: str):
        """Xác nhận giao dịch thành công (Atomic Commit)."""
        record = {
            "txn_id": txn_id, 
            "ts": time.time(), 
            "new_hash": new_hash,
            "status": "committed"
        }
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
    def rollback(self, txn_id: str, reason: str):
        """Hủy bỏ giao dịch nếu Gatekeeper chặn hoặc có lỗi."""
        record = {
            "txn_id": txn_id, 
            "ts": time.time(), 
            "status": "rolled_back",
            "reason": reason
        }
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def recover(self, driver_callback: Callable[[Dict[str, Any]], None]):
        """
        Khôi phục hệ thống sau sự cố (Crash Recovery).
        Quét các transaction "pending" và gọi driver_callback để Replay diễn lại.
        """
        print("[Journal] Khởi động tiến trình phục hồi (Crash Recovery)...")
        history = {}
        with open(self.journal_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                entry = json.loads(line)
                
                # Keep the latest state of the transaction
                if entry["txn_id"] not in history:
                    history[entry["txn_id"]] = entry
                else:
                    history[entry["txn_id"]].update(entry)
                    
        recovered_count = 0
        for txn_id, entry in history.items():
            if entry.get("status") == "pending":
                print(f"[Journal] Phát hiện giao dịch dở dang: {txn_id}. Đang Replay...")
                # Driver sẽ thực hiện lại mutation dựa trên dữ liệu node
                driver_callback(entry)
                recovered_count += 1
                
        if recovered_count == 0:
            print("[Journal] Trạng thái Memory an toàn. Không cần phục hồi.")
        else:
            print(f"[Journal] Đã phục hồi {recovered_count} giao dịch.")
