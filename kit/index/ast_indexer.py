import ast
import os
from pathlib import Path
from typing import Any, List, Optional

from kit.core.graph_store import GraphStore


class V1ASTIndexer(ast.NodeVisitor):
    def __init__(self, store: GraphStore) -> None:
        self.store = store
        self.current_file: Optional[str] = None
        self.module_path: List[str] = []
        self.current_symbol_id: Optional[int] = None

    def index_repo(self, root_path: str) -> None:
        """Quét toàn bộ thư mục và index các file .py"""
        for root, _, files in os.walk(root_path):
            for file in sorted(files):
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, root_path)
                    # Biến path thành module name: kit/core/auth.py -> kit.core.auth
                    module_name = rel_path.replace(os.path.sep, ".").removesuffix(".py")

                    # Ignore standard test/venv paths for clean graph
                    if "venv" in module_name or "test" in module_name:
                        continue

                    self.index_file(full_path, module_name)

    def index_file(self, file_path: str, module_name: str) -> None:
        self.current_file = file_path
        self.module_path = module_name.split(".")

        # Thêm module symbol như gợi ý cực kỳ đáng giá của user
        module_symbol_id = self.store.add_symbol(
            module_name, kind="module", file_path=self.current_file
        )
        # Sinh alias cho module
        self.store.add_alias(self.module_path[-1], module_symbol_id, confidence=0.7)
        if len(self.module_path) > 1:
            self.store.add_alias(
                self.module_path[-2] + "_" + self.module_path[-1],
                module_symbol_id,
                confidence=0.8,
            )

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
                self.visit(tree)
            except SyntaxError:
                pass  # Valid to silently skip

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        fqn = ".".join(self.module_path + [node.name])

        symbol_id = self.store.add_symbol(
            fqn, kind="class", file_path=self.current_file
        )
        self.store.add_alias(node.name, symbol_id, confidence=0.8)

        old_path = self.module_path
        self.module_path = self.module_path + [node.name]
        self.generic_visit(node)
        self.module_path = old_path

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        fqn = ".".join(self.module_path + [node.name])

        symbol_id = self.store.add_symbol(
            fqn, kind="function", file_path=self.current_file
        )

        # Thêm alias
        self.store.add_alias(node.name, symbol_id, confidence=0.9)
        if len(self.module_path) > 1:
            # Alias dạng Class.method
            class_method_alias = f"{self.module_path[-1]}.{node.name}"
            self.store.add_alias(class_method_alias, symbol_id, confidence=1.0)

        prev_symbol = self.current_symbol_id
        self.current_symbol_id = symbol_id
        self.generic_visit(node)
        self.current_symbol_id = prev_symbol

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_Call(self, node: ast.Call) -> None:
        if not self.current_symbol_id:
            return

        target_alias: Optional[str] = None
        if isinstance(node.func, ast.Name):
            target_alias = node.func.id
        elif isinstance(node.func, ast.Attribute):
            target_alias = node.func.attr

        if target_alias:
            self.store.add_edge_by_alias(
                self.current_symbol_id, target_alias, layer=0
            )  # Layer 0: calls

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self._extract_imports(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._extract_imports(node)

    def _extract_imports(self, node: Any) -> None:
        if not self.current_symbol_id:
            return
        # A simple heuristic for Layer 1: Imports within functions
        for alias in node.names:
            target_alias = alias.name.split(".")[-1]
            self.store.add_edge_by_alias(
                self.current_symbol_id, target_alias, layer=1
            )  # Layer 1: imports
