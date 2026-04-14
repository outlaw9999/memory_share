from kit.core.kernel_fsm import ExecutionFrame, ExecutionContract, ExecutionQueue
# Standard library only - No pytest

def test_frame_initialization():
    frame = ExecutionFrame(command="echo hello")
    assert frame.state == "queued"
    assert frame.id is not None
    assert "echo hello" in frame.command

def test_contract_validation_success():
    ExecutionContract.validate_transition("queued", "running")
    ExecutionContract.validate_transition("running", "success")
    ExecutionContract.validate_transition("success", "rolled_back")

def test_contract_validation_illegal():
    try:
        ExecutionContract.validate_transition("queued", "success")
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass

def test_queue_flow():
    queue = ExecutionQueue()
    f1 = ExecutionFrame(command="cmd1")
    f2 = ExecutionFrame(command="cmd2")
    
    queue.push(f1)
    queue.push(f2)
    
    next_f = queue.get_next_queued()
    assert next_f.command == "cmd1"
    
    next_f.update_state("running")
    
    next_f = queue.get_next_queued()
    assert next_f.command == "cmd2"

if __name__ == "__main__":
    test_frame_initialization()
    test_contract_validation_success()
    test_contract_validation_illegal()
    test_queue_flow()
    print("FSM Component Tests Passed (Pure Python).")
