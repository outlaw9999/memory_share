from kit.skills.base import BaseSkill, SkillInput, SkillOutput
from kit.skills.registry import SkillRegistry, register_skill
from kit.skills.runtime import ASRRuntime

# v1.2.4-LOCK: Skills are now procedural (YAML) or core-integrated.
SkillRegistry.discover_all()

__all__ = [
    "BaseSkill",
    "SkillInput",
    "SkillOutput",
    "SkillRegistry",
    "ASRRuntime",
    "register_skill",
]
