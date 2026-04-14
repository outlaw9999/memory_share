import time
import uuid
from dataclasses import dataclass, field
from typing import Literal, List, Optional, Dict

# v1.2.4-TITANIUM Execution State Machine
ExecutionState = Literal["queued", "running", "success", "failed", "rolled_back"]

@dataclass
class ExecutionFrame:
    """
    The atomic unit of execution in the KIT Deterministic Kernel.
    Encapsulates command, state, and results for a single operation.
    """
    command: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rollback_command: Optional[str] = None
    state: ExecutionState = "queued"
    retry_count: int = 0
    max_retries: int = 3
    
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    return_code: Optional[int] = None
    
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def update_state(self, new_state: ExecutionState):
        self.state = new_state
        self.updated_at = time.time()

class ExecutionContract:
    """
    Enforces invariant properties of the KIT Kernel.
    Validates state transitions and frame integrity.
    """
    
    ALLOWED_TRANSITIONS: Dict[str, List[ExecutionState]] = {
        "queued": ["running"],
        "running": ["success", "failed"],
        "failed": ["queued", "rolled_back"], # 'queued' for retry, 'rolled_back' if terminal
        "success": ["rolled_back"],         # Success can be rolled back if later steps fail
        "rolled_back": []                    # Terminal state
    }

    @staticmethod
    def validate_transition(from_state: ExecutionState, to_state: ExecutionState):
        if to_state not in ExecutionContract.ALLOWED_TRANSITIONS.get(from_state, []):
            raise RuntimeError(f"Illegal Kernel State Transition: {from_state} -> {to_state}")

    @staticmethod
    def validate_frame(frame: ExecutionFrame):
        if not frame.command.strip():
            raise ValueError("ExecutionFrame command cannot be empty or whitespace.")

class ExecutionQueue:
    """
    A linear sequence of ExecutionFrames to be processed by the Kernel.
    """
    def __init__(self):
        self._frames: List[ExecutionFrame] = []

    def push(self, frame: ExecutionFrame):
        ExecutionContract.validate_frame(frame)
        self._frames.append(frame)

    def get_next_queued(self) -> Optional[ExecutionFrame]:
        for frame in self._frames:
            if frame.state == "queued":
                return frame
        return None

    def get_history(self) -> List[ExecutionFrame]:
        return self._frames

    def get_successful_indices(self) -> List[int]:
        return [i for i, f in enumerate(self._frames) if f.state == "success"]
