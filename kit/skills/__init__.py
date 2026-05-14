from kit.skills.base import BaseSkill, SkillInput, SkillOutput
from kit.skills.registry import SkillRegistry, register_skill
from kit.skills.runtime import ASRRuntime

# 1.2.5LOCK: Skills are now procedural (YAML) or core-integrated.
SkillRegistry.discover_all()

__all__ = [
    "BaseSkill",
    "SkillInput",
    "SkillOutput",
    "SkillRegistry",
    "ASRRuntime",
    "register_skill",
]
