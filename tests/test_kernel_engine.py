from kit.core.kernel_fsm import ExecutionFrame
from kit.core.kernel_engine import DeterministicKernel
import time

def test_kernel_idempotency():
    kernel = DeterministicKernel()
    f1 = ExecutionFrame(command="echo first")
    f2 = ExecutionFrame(command="echo first") # Exact same command
    
    kernel.submit(f1)
    kernel.submit(f2)
    
    success = kernel.run()
    assert success is True
    assert f1.state == "success"
    assert f2.state == "success"
    # f2 should have been skipped in logs (we check state only here)

def test_kernel_retry():
    kernel = DeterministicKernel()
    # A command that will fail (assuming 'nonexistent_cmd' fails on this system)
    f1 = ExecutionFrame(command="nonexistent_cmd_xyz", max_retries=2)
    
    kernel.submit(f1)
    success = kernel.run()
    
    assert success is False
    assert f1.state == "failed"
    assert f1.retry_count == 2

def test_kernel_rollback():
    kernel = DeterministicKernel()
    
    f1 = ExecutionFrame(command="echo step1", rollback_command="echo undostep1")
    f2 = ExecutionFrame(command="nonexistent_cmd_again") # Will fail
    
    kernel.submit(f1)
    kernel.submit(f2)
    
    success = kernel.run()
    
    assert success is False
    assert f1.state == "rolled_back"
    assert f2.state == "failed"

if __name__ == "__main__":
    print("Running Kernel Engine Tests...")
    test_kernel_idempotency()
    test_kernel_retry()
    test_kernel_rollback()
    print("Kernel Engine Tests Passed.")
