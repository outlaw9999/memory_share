import hashlib
import inspect
import logging

from kit.skills.base import BaseSkill

logger = logging.getLogger("kit.skills.registry")


class SkillRegistry:
    """
    Deterministic Skill Discovery for ASR v1.
    Maintains a mapping of skill names to their implementations.
    """

    _instance: SkillRegistry | None = None
    _skills: dict[str, type[BaseSkill]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, skill_cls: type[BaseSkill]):
        """Register a skill class and calculate its structural fingerprint."""
        name = skill_cls.name

        # Calculate Hash for version pinning / integrity
        source = inspect.getsource(skill_cls)
        fingerprint = hashlib.sha256(source.encode()).hexdigest()[:12]

        logger.info(f"Registering skill: {name} v{skill_cls.version} [{fingerprint}]")
        cls._skills[name] = skill_cls

    @classmethod
    def get_skill(cls, name: str) -> type[BaseSkill] | None:
        return cls._skills.get(name)

    @classmethod
    def list_skills(cls) -> list[dict]:
        """List skills without triggering full class logic if possible."""
        return [
            {
                "name": name,
                "version": getattr(cls._skills[name], "version", "1.0.0"),
                "input_model": cls._skills[name].input_model.__name__
            }
            for name in cls._skills
        ]

    @classmethod
    def discover_all(cls):
        """
        Scan and auto-register all skills in the kit.skills package.
        Prevents 'Orphaned Capability' problems.
        """
        import importlib
        import pkgutil
        import kit.skills as skills_pkg
        
        logger.info("Initializing Auto-Skill Discovery...")
        for loader, module_name, is_pkg in pkgutil.walk_packages(skills_pkg.__path__, skills_pkg.__name__ + "."):
            try:
                # Import the module; decorators (@register_skill) will handle registration
                importlib.import_module(module_name)
            except Exception as e:
                logger.warning(f"Failed to auto-discover skill module {module_name}: {e}")


def register_skill(skill_cls: type[BaseSkill]):
    """Decorator for easy registration."""
    SkillRegistry.register(skill_cls)
    return skill_cls
