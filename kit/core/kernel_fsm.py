import time
import uuid
from dataclasses import dataclass, field
from typing import Literal, List, Optional, Dict

# v1.2.4-TITANIUM Execution State Machine
ExecutionState = Literal["queued", "running", "success", "failed", "rolled_back"]

@dataclass(frozen=True)
class FlowExecutionContext:
    """Isolation boundary for a flow step execution (v0.1.2)."""
    flow_id: str
    step_id: str
    transaction_id: str
    attempt: int
    is_dry_run: bool = False
    is_committable: bool = True


@dataclass
class ExecutionFrame:
    """
    The atomic unit of execution in the KIT Deterministic Kernel.
    Encapsulates command (or internal action), state, and results.
    """
    command: Optional[str] = None
    action: Optional[Any] = None # For internal Python calls (ECL v1)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    rollback_command: Optional[str] = None
    state: ExecutionState = "queued"
    retry_count: int = 0
    max_retries: int = 3
    
    # Flow Context Integration (v0.1.2)
    context: Optional[FlowExecutionContext] = None
    
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
        "failed": ["queued", "rolled_back"],
        "success": ["rolled_back"],
        "rolled_back": []
    }

    @staticmethod
    def validate_transition(from_state: ExecutionState, to_state: ExecutionState):
        if to_state not in ExecutionContract.ALLOWED_TRANSITIONS.get(from_state, []):
            raise RuntimeError(f"Illegal Kernel State Transition: {from_state} -> {to_state}")

    @staticmethod
    def validate_frame(frame: ExecutionFrame):
        if not frame.command and not frame.action:
            raise ValueError("ExecutionFrame must have either a command or an internal action.")

class StateMutationContract:
    """
    ECL v1: Deterministic State Mutation Contract.
    Ensures every mutation to SAMBrain is governed by a Frame.
    """
    @staticmethod
    def authorize_mutation(frame: Optional[ExecutionFrame]):
        if frame is None:
            # v1.2.4 Mode: Allow but Logan telemetry as 'UNGOVERNED'
            # (In v2.0 TITANIUM, this will raise an error)
            return "UNGOVERNED"
        
        if frame.state != "running":
            raise RuntimeError(f"Mutation unauthorized: Frame {frame.id} is in state '{frame.state}', not 'running'.")
        
        return frame.id

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
