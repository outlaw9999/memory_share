import json
import os
import uuid
import time
from pathlib import Path
from typing import Callable, Dict, Any, List

class MemoryConflictError(Exception):
    pass

class JournalEngine:
    """
    Event Stream Write-Ahead Log (WAL) Journal Engine cho Antigravity Memory Kernel.
    Sử dụng mô hình Event Stream (intent -> commit/rollback) để an toàn tuyệt đối.
    """
    def __init__(self, workspace_root: str):
        self.antigravity_dir = Path(workspace_root) / ".antigravity"
        self.memory_dir = self.antigravity_dir / "memory"
        self.journal_path = self.memory_dir / "journal.jsonl"
        self.txn_state_path = self.memory_dir / "txn_state.json"
        
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path.touch(exist_ok=True)
        
    def _read_txn_state(self) -> Dict[str, Any]:
        if self.txn_state_path.exists():
            try:
                with open(self.txn_state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {}

    def _write_txn_state(self, state: Dict[str, Any]):
        # Atomic write cho txn_state
        tmp = self.txn_state_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, self.txn_state_path)

    def log_intent(self, agent_id: str, target_file: str, operation: str, node_data: Dict[str, Any], old_hash: str) -> str:
        """
        Gửi yêu cầu thay đổi (Intent). 
        Bắt buộc kèm `old_hash` để thực thi Optimistic Concurrency Control.
        """
        txn_id = str(uuid.uuid4())
        record = {
            "type": "intent",
            "txn_id": txn_id,
            "ts": time.time(),
            "agent": agent_id,
            "target": target_file,
            "op": operation,
            "node": node_data,
            "old_hash": old_hash
        }
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return txn_id

    def commit(self, txn_id: str, new_hash: Optional[str] = None):
        """Xác nhận giao dịch thành công (Atomic Commit)."""
        record = {
            "type": "commit",
            "txn_id": txn_id, 
            "ts": time.time(),
            "new_hash": new_hash
        }
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
    def rollback(self, txn_id: str, reason: str):
        """Hủy bỏ giao dịch."""
        record = {
            "type": "rollback",
            "txn_id": txn_id, 
            "ts": time.time(), 
            "reason": reason
        }
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def recover(self, driver_replay_callback: Callable[[Dict[str, Any]], None]):
        """
        Khôi phục hệ thống (Sử dụng State Machine).
        """
        print("[Journal] Khởi động tiến trình phục hồi (Crash Recovery)...")
        
        # Build State Machine từ Log
        transactions = {}
        with open(self.journal_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                entry = json.loads(line)
                
                txn_id = entry["txn_id"]
                tx = transactions.setdefault(txn_id, {"status": None})
                
                if entry["type"] == "intent":
                    tx["intent"] = entry
                    tx["status"] = "pending"
                    
                elif entry["type"] == "commit":
                    tx["status"] = "committed"
                    
                elif entry["type"] == "rollback":
                    tx["status"] = "rolled_back"
                    
        recovered_count = 0
        active_state = {}
        
        for txn_id, tx in transactions.items():
            active_state[txn_id] = tx["status"]
            
            if tx["status"] == "pending":
                print(f"[Journal] Phát hiện giao dịch dở dang: {txn_id}. Đang Replay...")
                try:
                    driver_replay_callback(tx["intent"])
                    self.commit(txn_id) # Đánh dấu lại là commit sau khi replay thành công
                    active_state[txn_id] = "committed"
                    recovered_count += 1
                except MemoryConflictError:
                    print(f"[Journal] Replay thất bại cho {txn_id} do Memory Conflict (old_hash mismatch). Rolling back.")
                    self.rollback(txn_id, "replay_conflict")
                    active_state[txn_id] = "rolled_back"
                
        # Cache trạng thái để boot nhanh hơn lần sau
        self._write_txn_state(active_state)
        
        if recovered_count == 0:
            print("[Journal] Trạng thái Memory an toàn. Không cần phục hồi.")
        else:
            print(f"[Journal] Đã phục hồi {recovered_count} giao dịch.")
