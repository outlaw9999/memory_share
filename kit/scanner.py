import ast
from pathlib import Path
from typing import List, Union

from .models import CallSite, Symbol


class Scanner:
    """Lightweight symbol scanner.

    This starts with Python support via the stdlib AST and can later be
    swapped for Tree-sitter without changing the AtlasIndexer contract.
    """

    def scan_file(self, path: Union[str, Path]) -> List[Symbol]:
        file_path = Path(path)
        module = self._parse_module(file_path)
        if module is None:
            return []

        symbols: List[Symbol] = []
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(Symbol(node.name, "function", str(file_path), node.lineno))
            elif isinstance(node, ast.ClassDef):
                symbols.append(Symbol(node.name, "class", str(file_path), node.lineno))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols.append(Symbol(alias.name, "import", str(file_path), node.lineno))
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                for alias in node.names:
                    qualified = f"{module_name}.{alias.name}" if module_name else alias.name
                    symbols.append(Symbol(qualified, "import", str(file_path), node.lineno))
        return symbols

    def scan_calls(self, path: Union[str, Path]) -> List[CallSite]:
        file_path = Path(path)
        module = self._parse_module(file_path)
        if module is None:
            return []

        calls: List[CallSite] = []
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls.extend(self._collect_calls(file_path, node.name, node))
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        calls.extend(self._collect_calls(file_path, f"{node.name}.{member.name}", member))
        return calls

    def _collect_calls(self, file_path: Path, caller: str, node: ast.AST) -> List[CallSite]:
        calls: List[CallSite] = []
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            callee = self._extract_callee_name(inner.func)
            if callee:
                calls.append(CallSite(caller, callee, str(file_path), inner.lineno))
        return calls

    def _extract_callee_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._extract_callee_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    def _parse_module(self, file_path: Path) -> ast.Module | None:
        if not file_path.exists() or file_path.suffix != ".py":
            return None

        try:
            source = file_path.read_text(encoding="utf-8")
            return ast.parse(source, filename=str(file_path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return None
