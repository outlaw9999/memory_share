import logging
import time
import traceback
from typing import Any

from kit.core.state_vector import StateVector
from kit.skills.base import SkillOutput
from kit.skills.registry import SkillRegistry

logger = logging.getLogger("kit.skills.runtime")


class ASRRuntime:
    """
    Agent Skill Runtime (ASR).
    The heart of the Action Projection Layer (APL).
    Mediates between the Kernel context and Skill execution.
    """

    def __init__(self):
        self.trace_buffer: list[dict] = []

    def execute(self, skill_name: str, input_data: dict[str, Any], context: list[StateVector]) -> SkillOutput:
        """
        The ASR Execution Pipeline:
        1. Discovery
        2. Context Injection
        3. Execution (Sanitized)
        4. Capture Trace
        """
        start_time = time.perf_counter()

        # 1. Discovery
        skill_cls = SkillRegistry.get_skill(skill_name)
        if not skill_cls:
            return SkillOutput(status="ERROR", results={"message": f"Skill '{skill_name}' not found"})

        try:
            # 2. Preparation (No side-effects enforced via contract)
            # v1.2.5: Deterministic input hydration
            validated_input = skill_cls.input_model(**input_data)
            skill_instance = skill_cls()

            # 3. Execution (Pure Function Boundary)
            # We don't pass the brain or db. Only StateVectors.
            output = skill_instance.run(validated_input, context)

            # 4. Capture Trace for debugging
            execution_time = (time.perf_counter() - start_time) * 1000
            output.execution_time_ms = execution_time

            self._log_trace(skill_name, input_data, output)
            return output

        except Exception as e:
            logger.error(f"Skill execution failed: {skill_name} - {str(e)}")
            return SkillOutput(status="CRASHED", results={"error": str(e), "traceback": traceback.format_exc()})

    def _log_trace(self, name: str, input_data: dict, output: SkillOutput):
        """
        Record execution trace with strict capacity limit.
        """
        trace = {
            "skill": name,
            "status": output.status,
            "observations_count": len(output.proposed_observations),
            "signals_count": len(output.signals),
            "time_ms": round(output.execution_time_ms, 2),
        }
        self.trace_buffer.append(trace)

        # v1.2.5-LOCK: Circular buffer enforcement (Max 50 traces)
        if len(self.trace_buffer) > 50:
            self.trace_buffer.pop(0)

    def clear_traces(self):
        """Manual memory cleanup for heavy sessions."""
        self.trace_buffer.clear()
