import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
from kit.core.kernel_engine import DeterministicKernel
from kit.core.kernel_fsm import ExecutionFrame, FlowExecutionContext

logger = logging.getLogger("kit.flow.engine")

@dataclass
class FlowStep:
    id: str
    command: str
    depends_on: List[str] = field(default_factory=list)
    retry: int = 3
    idempotent: bool = True
    mode: str = "read"
    args: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FlowSpec:
    id: str
    name: str
    version: str = "0.1.2"
    mode: str = "strict"
    steps: List[FlowStep] = field(default_factory=list)

class TransactionManager:
    """Pure metadata layer for tracking atomic execution units (v0.1.2)."""
    
    def __init__(self, brain: Any):
        self.brain = brain

    def start_transaction(self, flow_id: str, step_id: str, attempt: int) -> FlowExecutionContext:
        transaction_id = f"tx-{uuid.uuid4().hex[:8]}"
        # Persistent record in flow_transactions table
        with self.brain.get_connection() as conn:
            conn.execute(
                "INSERT INTO flow_transactions (id, flow_id, step_id, state) VALUES (?, ?, ?, 'open')",
                (transaction_id, flow_id, step_id)
            )
        return FlowExecutionContext(
            flow_id=flow_id,
            step_id=step_id,
            transaction_id=transaction_id,
            attempt=attempt
        )

    def commit_transaction(self, ctx: FlowExecutionContext):
        with self.brain.get_connection() as conn:
            conn.execute(
                "UPDATE flow_transactions SET state = 'committed', finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (ctx.transaction_id,)
            )

    def fail_transaction(self, ctx: FlowExecutionContext):
        with self.brain.get_connection() as conn:
            conn.execute(
                "UPDATE flow_transactions SET state = 'failed', finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (ctx.transaction_id,)
            )

class FlowPlanner:
    """Resolves DAG and builds an execution plan."""
    
    @staticmethod
    def load(path: Path) -> FlowSpec:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        flow_data = data.get("flow", {})
        steps = []
        for s in flow_data.get("steps", []):
            steps.append(FlowStep(
                id=s["id"],
                command=s["command"],
                depends_on=s.get("depends_on", []),
                retry=s.get("retry", 3),
                idempotent=s.get("idempotent", True),
                mode=s.get("mode", "read"),
                args=s.get("args", {})
            ))
            
        return FlowSpec(
            id=flow_data.get("id", uuid.uuid4().hex[:8]),
            name=flow_data.get("name", "anonymous_flow"),
            mode=flow_data.get("mode", "strict"),
            steps=steps
        )

    def resolve_dag(self, spec: FlowSpec) -> List[FlowStep]:
        """Simple topological sort for DAG resolution."""
        resolved = []
        visited = set()
        step_map = {s.id: s for s in spec.steps}
        
        def visit(step_id: str, ancestors: Set[str]):
            if step_id in ancestors:
                raise ValueError(f"Circular dependency detected at step: {step_id}")
            if step_id in visited:
                return
            
            step = step_map.get(step_id)
            if not step:
                raise ValueError(f"Unknown dependency: {step_id}")
            
            new_ancestors = ancestors | {step_id}
            for dep in step.depends_on:
                visit(dep, new_ancestors)
            
            visited.add(step_id)
            resolved.append(step)

        for step in spec.steps:
            visit(step.id, set())
            
        return resolved

class FlowCommitController:
    """Enforces transaction boundaries and final bake logic."""
    
    def __init__(self, brain: Any):
        self.brain = brain

    def finalize(self, flow_id: str):
        """Bake all observations associated with this flow."""
        logger.info(f"Finalizing Flow {flow_id}: Baking side-effects...")
        with self.brain.get_connection() as conn:
            # Atomic bake: Flip is_baked=1 for all observations with this flow_id in metadata
            # We use a JSON search for flow_id in the metadata column
            # Note: SQLite's json_extract is efficient here
            conn.execute("""
                UPDATE observations 
                SET is_baked = 1 
                WHERE is_baked = 0 
                  AND json_extract(metadata, '$._flow_id') = ?
            """, (flow_id,))
            
            conn.execute(
                "UPDATE flow_runs SET state = 'success', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (flow_id,)
            )

class FlowExecutor:
    """Orchestrates the execution of a FlowSpec through the DeterministicKernel."""
    
    def __init__(self, brain: Any):
        self.brain = brain
        self.tx_manager = TransactionManager(brain)
        self.commit_controller = FlowCommitController(brain)
        self.kernel = DeterministicKernel(session_id=f"flow-{uuid.uuid4().hex[:6]}")
        self.kernel.bind_brain(brain)

    def execute(self, spec: FlowSpec) -> bool:
        import sys
        planner = FlowPlanner()
        ordered_steps = planner.resolve_dag(spec)
        
        # 1. Initialize Flow Run in DB
        with self.brain.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO flow_runs (id, name, state) VALUES (?, ?, 'running')",
                (spec.id, spec.name)
            )
            for step in ordered_steps:
                conn.execute(
                    "INSERT OR IGNORE INTO flow_steps (id, flow_id, step_id, command, depends_on, idempotent, max_retries) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"{spec.id}:{step.id}", spec.id, step.id, step.command, ",".join(step.depends_on), step.idempotent, step.retry)
                )

        # 2. Iterate and Execute
        from kit.core.kit_env import get_venv_path
        venv = get_venv_path()
        if venv and sys.platform == "win32":
            python_exe = str(venv / "Scripts" / "python.exe")
        elif venv:
            python_exe = str(venv / "bin" / "python")
        else:
            python_exe = sys.executable
            
        # v1.2.5-LOCK: Reify 'kit' to absolute module execution if possible
        kit_reified = f"{python_exe} -m kit.cli.main"

        for step in ordered_steps:
            # Idempotency Check (Level 1)
            if step.idempotent:
                with self.brain.get_connection() as conn:
                    row = conn.execute(
                        "SELECT state FROM flow_steps WHERE id = ?",
                        (f"{spec.id}:{step.id}",)
                    ).fetchone()
                    if row and row["state"] == "success":
                        logger.info(f"Step {step.id} already success. Skipping (Idempotency).")
                        continue

            # Start Transaction
            ctx = self.tx_manager.start_transaction(spec.id, step.id, attempt=0)
            
            # Reify command
            reified_cmd = step.command
            if reified_cmd.startswith("kit "):
                reified_cmd = reified_cmd.replace("kit ", f"{kit_reified} ", 1)
            elif reified_cmd == "kit":
                reified_cmd = kit_reified

            # Context Propagation via Environment
            flow_env = os.environ.copy()
            flow_env["KIT_FLOW_ID"] = ctx.flow_id
            flow_env["KIT_STEP_ID"] = ctx.step_id
            flow_env["KIT_TRANSACTION_ID"] = ctx.transaction_id

            frame = ExecutionFrame(
                command=reified_cmd,
                context=ctx,
                max_retries=step.retry
            )
            
            logger.info(f"Executing step {step.id}: {reified_cmd}")
            self.kernel.submit(frame)
            success = self.kernel.run(env=flow_env)
            
            if success:
                self.tx_manager.commit_transaction(ctx)
                with self.brain.get_connection() as conn:
                    conn.execute(
                        "UPDATE flow_steps SET state = 'success', frame_id = ? WHERE id = ?",
                        (frame.id, f"{spec.id}:{step.id}")
                    )
            else:
                # Log error details to metadata
                import json
                error_meta = {"stderr": frame.stderr, "return_code": frame.return_code}
                with self.brain.get_connection() as conn:
                    conn.execute(
                        "UPDATE flow_transactions SET state = 'failed', finished_at = CURRENT_TIMESTAMP, metadata = ? WHERE id = ?",
                        (json.dumps(error_meta), ctx.transaction_id)
                    )
                
                self.tx_manager.fail_transaction(ctx)
                with self.brain.get_connection() as conn:
                    conn.execute(
                        "UPDATE flow_steps SET state = 'failed', frame_id = ? WHERE id = ?",
                        (frame.id, f"{spec.id}:{step.id}")
                    )
                
                logger.error(f"Step {step.id} failed with code {frame.return_code}")
                if frame.stderr:
                    logger.error(f"Error output:\n{frame.stderr}")
                
                return False

        # 3. Final Commit (Bake)
        self.commit_controller.finalize(spec.id)
        return True
