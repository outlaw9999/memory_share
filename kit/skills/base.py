from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from kit.core.state_vector import StateVector
from kit.models.signal import Signal

T_in = TypeVar("T_in", bound=BaseModel)


class SkillInput(BaseModel):
    """Base model for all skill parameters."""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillOutput(BaseModel):
    """
    Standardized Epistemic Proposal.
    Skills do not learn; they propose.
    """
    status: str = "SUCCESS"
    results: dict[str, Any] = Field(default_factory=dict)
    proposed_observations: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    execution_time_ms: float = 0.0


class BaseSkill[T_in](ABC):
    """
    Action Projection Layer (APL) - Skill Contract.
    Strictly Stateless. Pure Function over StateVector Context.
    """

    name: str
    version: str = "1.0.0"
    input_model: type[T_in]

    @abstractmethod
    def run(self, input_data: T_in, context: list[StateVector]) -> SkillOutput:
        """
        Execute the action primitive.
        NO direct Brain access. NO DB handles.
        """
        pass
