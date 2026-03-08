import ast
from pathlib import Path
from typing import List, Union

from .models import Symbol


class Scanner:
    """Lightweight symbol scanner.

    This starts with Python support via the stdlib AST and can later be
    swapped for Tree-sitter without changing the AtlasIndexer contract.
    """

    def scan_file(self, path: Union[str, Path]) -> List[Symbol]:
        file_path = Path(path)
        if not file_path.exists() or file_path.suffix != ".py":
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
            module = ast.parse(source, filename=str(file_path))
        except (OSError, SyntaxError, UnicodeDecodeError):
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
