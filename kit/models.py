from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    file: str
    line: int


@dataclass(frozen=True)
class CallSite:
    caller: str
    callee: str
    file: str
    line: int


def build_symbol_id(path: str, name: str, scope: str | None = None) -> str:
    """
    Phase 10: Build a file-qualified symbol identity.
    
    Identity contract: file::scope::name
    This ensures each symbol is uniquely identified by its location and name.
    
    Args:
        path: File path (absolute or relative)
        name: Symbol name
        scope: Optional scope (defaults to 'module')
    
    Returns:
        symbol_id: Unique identifier in format "file::scope::name"
    
    Example:
        build_symbol_id("parser_a.py", "parse") → "parser_a.py::module::parse"
        build_symbol_id("pkg/service.py", "handle", "class_method") → "pkg/service.py::class_method::handle"
    """
    scope = scope or "module"
    # Normalize path to use forward slashes for consistency
    normalized_path = str(Path(path)).replace("\\", "/")
    return f"{normalized_path}::{scope}::{name}"
