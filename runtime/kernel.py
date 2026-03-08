import time
from pathlib import Path
from typing import Optional, Dict, Any

from runtime.lock_manager import LockManager
from runtime.journal_engine import JournalEngine, MemoryConflictError
from runtime.ast_parser import ASTMarkdownParser

class AntigravityKernel:
    """
    The Core API for the Antigravity Memory Kit.
    Enforces Atomicity, Consistency, Isolation, and Durability (ACID) 
    for AI Agent memory operations.
    """
    def __init__(self, workspace_root: str):
        self.root = Path(workspace_root)
        self.lock_manager = LockManager(workspace_root)
        self.journal = JournalEngine(workspace_root)
        
    def write_memory(self, 
                     agent_id: str, 
                     target_file: str, 
                     node_id: str, 
                     new_content: str, 
                     expected_hash: Optional[str] = None) -> bool:
        """
        Standardized Safe Write Path for Agents.
        Implements Cognitive Conflict Detection via expected_hash (OCC).
        """
        # 1. Acquire Lock
        lock_id = self.lock_manager.wait_and_acquire(agent_id, target_file, timeout=10)
        if not lock_id:
            print(f"[Kernel] ERROR: Could not acquire lock for {target_file}")
            return False
            
        try:
            # 2. Init Parser and Check Hash (OCC)
            parser = ASTMarkdownParser(self.root / target_file)
            current_hash = parser.get_hash()
            
            if expected_hash and current_hash != expected_hash:
                reason = f"Hash Mismatch! Current: {current_hash[:8]}, Expected: {expected_hash[:8]}"
                print(f"[Kernel] REJECTED: {reason}")
                self.journal.rollback(str(time.time()), reason) # Mock txn_id for rollback
                return False

            # 3. Log Semantic Intent
            node_data = {"node_id": node_id, "content_preview": new_content[:50] + "..."}
            txn_id = self.journal.log_intent(agent_id, target_file, "update_node", node_data, current_hash)
            
            # 4. Mutate AST
            success = parser.update_node(node_id, new_content)
            if not success:
                # If node doesn't exist, maybe assume it's a new node (append) 
                # or fail based on policy. Let's fail for the "Standard" version.
                print(f"[Kernel] ERROR: Node {node_id} not found.")
                self.journal.rollback(txn_id, "node_not_found")
                return False
                
            # 5. Commit to Shadow/Disk
            parser.commit()
            
            # 6. Finalize Journal
            new_hash = parser.get_hash()
            self.journal.commit(txn_id, new_hash)
            print(f"[Kernel] SUCCESS: Transaction {txn_id} committed.")
            return True
            
        except Exception as e:
            print(f"[Kernel] CRITICAL ERROR: {e}")
            return False
        finally:
            # 7. Always Release
            self.lock_manager.release(agent_id, lock_id, target_file)

if __name__ == "__main__":
    # Internal Unit Test
    kernel = AntigravityKernel("c:/Users/Admin/.gemini/antigravity/playground/memory_share")
    
    # Pre-requisite: Create a file with a node
    test_file = Path("c:/Users/Admin/.gemini/antigravity/playground/memory_share/brain/layer2_core/auth.md")
    if not test_file.exists():
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("<!-- node:id=auth-decisions -->\n## Auth Decisions\nInitial state.\n", encoding="utf-8")
    
    # 1. Successful Write
    h1 = ASTMarkdownParser(test_file).get_hash()
    kernel.write_memory("agent_alpha", "brain/layer2_core/auth.md", "auth-decisions", "OAuth2 Flow implemented.", h1)
    
    # 2. Conflicting Write (OCC Failure)
    kernel.write_memory("agent_beta", "brain/layer2_core/auth.md", "auth-decisions", "Force JWT instead.", h1)
