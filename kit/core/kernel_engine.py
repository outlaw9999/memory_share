import hashlib
import subprocess
import time
from typing import Dict, Set, Optional, List
from kit.core.kernel_fsm import ExecutionFrame, ExecutionQueue, ExecutionContract

class DeterministicKernel:
    """
    The TITANIUM Execution Engine.
    Processes a queue of ExecutionFrames with Idempotency, Retry, and Rollback logic.
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self.queue = ExecutionQueue()
        self.session_id = session_id or str(hash(time.time()))
        self.brain: Optional[Any] = None # Will hold SAMBrain instance
        
        # Idempotency Lock: Commands that succeeded in this session
        self._idempotency_set: Set[str] = set()
        
        # Mapping of Frame ID to Frame for lookup
        self._frame_index: Dict[str, ExecutionFrame] = {}

    def bind_brain(self, brain: Any):
        self.brain = brain

    def submit(self, frame: ExecutionFrame):
        frame.session_id = self.session_id
        self.queue.push(frame)
        self._frame_index[frame.id] = frame

    def _get_command_hash(self, cmd: str) -> str:
        return hashlib.sha256(cmd.strip().encode()).hexdigest()

    def run(self) -> bool:
        """
        Executes the queue. Returns True if all frames succeed, False otherwise.
        Triggers rollback on terminal failure.
        """
        while True:
            frame = self.queue.get_next_queued()
            if not frame:
                break
            
            # 1. Idempotency Check
            cmd_hash = self._get_command_hash(frame.command)
            if cmd_hash in self._idempotency_set:
                print(f"  [Kernel] Idempotency Hit: Skipping '{frame.command[:30]}...' (Session Success)")
                frame.update_state("success")
                continue

            # 2. Transition to Running
            ExecutionContract.validate_transition(frame.state, "running")
            frame.update_state("running")
            
            # ECL v1: Bind frame to brain context for side-effect tracking
            if self.brain:
                self.brain.active_frame = frame
                
            print(f"  [Kernel] Running Frame: {frame.command[:50]}...")

            # 3. Execution
            success = self._execute_frame(frame)

            if success:
                ExecutionContract.validate_transition(frame.state, "success")
                frame.update_state("success")
                self._idempotency_set.add(cmd_hash)
            else:
                # 4. Retry Logic
                ExecutionContract.validate_transition(frame.state, "failed")
                frame.update_state("failed")
                
                if frame.retry_count < frame.max_retries:
                    frame.retry_count += 1
                    backoff = frame.retry_count * 1 # Simple linear backoff
                    print(f"  [Kernel] Frame Failed. Retrying in {backoff}s... ({frame.retry_count}/{frame.max_retries})")
                    time.sleep(backoff)
                    ExecutionContract.validate_transition(frame.state, "queued")
                    frame.update_state("queued")
                else:
                    # 5. Terminal Failure -> Rollback
                    print(f"  [Kernel] TERMINAL FAILURE: {frame.command[:50]}")
                    self._trigger_rollback()
                    return False
        
        return True

    def _execute_frame(self, frame: ExecutionFrame) -> bool:
        try:
            # ECL v1: Handle Internal Actions (Python)
            if frame.action:
                result = frame.action()
                # Action should return True/False or a result object with .returncode
                if hasattr(result, "returncode"):
                     frame.return_code = result.returncode
                     return result.returncode == 0
                return bool(result)

            # Standard Shell Execution
            # Note: We use shell=True for complex Windows commands/pip logic
            result = subprocess.run(
                frame.command,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8', 
                errors='replace'
            )
            frame.stdout = result.stdout
            frame.stderr = result.stderr
            frame.return_code = result.returncode
            
            # ECL v1: Clear context after primary execution
            if self.brain:
                self.brain.active_frame = None
                
            return result.returncode == 0
        except Exception as e:
            if self.brain:
                self.brain.active_frame = None
            frame.stderr = str(e)
            frame.return_code = -1
            return False

    def _trigger_rollback(self):
        """
        Iterates backwards through successful frames and executes their rollback commands.
        """
        print("\n" + "!"*40)
        print(" [Kernel] INITIATING ROLLBACK ENGINE")
        print("!"*40)
        
        history = self.queue.get_history()
        # Find all successful frames before the failure
        successful_frames = [f for f in history if f.state == "success"]
        
        for frame in reversed(successful_frames):
            if frame.rollback_command:
                print(f"  [Rollback] Executing: {frame.rollback_command}")
                try:
                    subprocess.run(frame.rollback_command, shell=True, capture_output=True, text=True)
                except:
                    pass
            else:
                print(f"  [Rollback] No rollback defined for: {frame.command[:30]}... (Skipping)")
            
            ExecutionContract.validate_transition(frame.state, "rolled_back")
            frame.update_state("rolled_back")
            
        print(" [Kernel] ROLLBACK COMPLETE.")
        
        # BUGFIX: Auto-unseal after rollback to restore write capability
        self._auto_unseal()
    
    def _auto_unseal(self):
        """Auto-unseal after rollback recovery."""
        try:
            from kit.core.kit_lock import unseal, is_sealed
            from pathlib import Path
            
            root = Path.cwd()
            if is_sealed(root):
                print("  [Rollback] Auto-unsealing system...")
                try:
                    unseal(Path(".kit/local_brain.db"), root, "rollback_recovery")
                    print("  [Rollback] Write path restored.")
                except Exception as e:
                    print(f"  [Rollback] Auto-unseal failed: {e}")
        except ImportError:
            pass
