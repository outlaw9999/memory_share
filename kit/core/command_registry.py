# .kit v1.2.4 - Command Registry Spec v1
# Hierarchical Command Architecture with Explicit Contracts

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, List
from enum import StrEnum

class CommandSideEffect(StrEnum):
    READ_ONLY = "READ_ONLY"
    MUTATION = "MUTATION"
    DESTRUCTIVE = "DESTRUCTIVE"

class CommandNamespace(StrEnum):
    CORE = "core"
    MEMORY = "memory"
    DIAGNOSTIC = "diagnostic"
    RUNTIME = "runtime"
    META = "meta"
    SEARCH = "search"

@dataclass(frozen=True)
class CommandContract:
    """Metadata layer defining the execution behavior of a command."""
    name: str
    namespace: CommandNamespace
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    side_effect: CommandSideEffect = CommandSideEffect.READ_ONLY
    io_safe: bool = True

class CommandRegistry:
    """Centralized Registry for kit commands (v1.2.4-TITANIUM)."""
    
    _instance: Optional['CommandRegistry'] = None
    
    def __init__(self):
        self._commands: Dict[str, tuple[CommandContract, Callable]] = {}

    @classmethod
    def get_instance(cls) -> 'CommandRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, contract: CommandContract, handler: Callable):
        """Register a command with its contract and handler."""
        self._commands[contract.name] = (contract, handler)

    def get_command(self, name: str) -> Optional[tuple[CommandContract, Callable]]:
        return self._commands.get(name)

    def list_commands(self, namespace: Optional[CommandNamespace] = None) -> List[CommandContract]:
        if namespace:
            return [c for c, _ in self._commands.values() if c.namespace == namespace]
        return [c for c, _ in self._commands.values()]

    def get_help_tree(self) -> Dict[str, List[CommandContract]]:
        """Organize commands by namespace for grouped help output."""
        tree: Dict[str, List[CommandContract]] = {}
        for ns in CommandNamespace:
            tree[ns.value] = self.list_commands(ns)
        return tree

# --- Global Registry Instance ---
registry = CommandRegistry.get_instance()

def kit_command(
    name: str,
    namespace: CommandNamespace,
    description: str,
    side_effect: CommandSideEffect = CommandSideEffect.READ_ONLY,
    io_safe: bool = True,
    input_schema: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
):
    """Decorator for easy command registration."""
    def decorator(func: Callable):
        contract = CommandContract(
            name=name,
            namespace=namespace,
            description=description,
            side_effect=side_effect,
            io_safe=io_safe,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
        )
        registry.register(contract, func)
        return func
    return decorator
