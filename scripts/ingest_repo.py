import argparse
import ast
import os
import re
from pathlib import Path

from kit import api


class CodebaseIngestor:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).absolute()
        self.brain_initialized = False

    def setup_brain(self):
        if not self.brain_initialized:
            api.init_kernel()
            self.brain_initialized = True

    def scan(self):
        print(f"🚀 Ingesting codebase: {self.root_dir}")
        self.setup_brain()
        
        for root, _, files in os.walk(self.root_dir):
            if any(part.startswith('.') or part == "__pycache__" for part in Path(root).parts):
                continue
                
            for file in files:
                if file.endswith(".py"):
                    self.process_file(Path(root) / file)

    def process_file(self, file_path: Path):
        rel_path = file_path.relative_to(self.root_dir)
        module_path = str(rel_path).replace(os.sep, ".").removesuffix(".py")
        
        print(f"  📄 Processing {rel_path}...")
        
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                
            # 1. AST Analysis (Entities & Structure)
            tree = ast.parse(content)
            self.ingest_ast(tree, module_path, rel_path)
            
            # 2. Heuristic Analysis (Comments & TODOs)
            self.ingest_heuristics(content, module_path, rel_path)
            
        except Exception as e:
            print(f"    ❌ Error processing {rel_path}: {e}")

    def ingest_ast(self, tree, module_path, rel_path):
        # Register module as an entity
        api.learn(module_path, f"Python module located at {rel_path}", kind="module", layer="semantic")
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_uid = f"{module_path}.{node.name}"
                api.learn(class_uid, f"Class {node.name} defined in {module_path}", kind="class", layer="semantic")
                api.link(module_path, class_uid, "CONTAINS")
                
                # Extract Docstring
                doc = ast.get_docstring(node)
                if doc:
                    api.learn(class_uid, doc.strip(), kind="arch", layer="semantic", importance=0.8)
                    
            elif isinstance(node, ast.FunctionDef):
                func_uid = f"{module_path}.{node.name}"
                api.learn(func_uid, f"Function {node.name} in {module_path}", kind="function", layer="semantic")
                api.link(module_path, func_uid, "CONTAINS")
                
                doc = ast.get_docstring(node)
                if doc:
                    api.learn(func_uid, doc.strip(), kind="arch", layer="semantic", importance=0.7)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Ensure target exists as a placeholder
                    api.learn(node.module, f"External or unindexed module: {node.module}", kind="module", layer="semantic")
                    api.link(module_path, node.module, "DEPENDS_ON")
            
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    api.learn(alias.name, f"Imported module: {alias.name}", kind="module", layer="semantic")
                    api.link(module_path, alias.name, "DEPENDS_ON")

    def ingest_heuristics(self, content, module_path, rel_path):
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            # Working Memory: TODOs/FIXMEs
            todo_match = re.search(r"#\s*(TODO|FIXME|XXX):\s*(.*)", line, re.I)
            if todo_match:
                task_content = todo_match.group(2).strip()
                api.learn(module_path, f"Line {i+1}: {task_content}", kind="task", layer="working", importance=0.9)
                
            # Procedural: Internal comments explaining "How" or "Why"
            # Heuristic: Comments that are not at the start of the line or are on their own line but descriptive
            proc_match = re.search(r"#\s*(Note|Key|Ref|Why):\s*(.*)", line, re.I)
            if proc_match:
                proc_content = proc_match.group(2).strip()
                api.learn(module_path, proc_content, kind="procedural", layer="procedural", importance=0.6)

def main():
    parser = argparse.ArgumentParser(description="Ingest a Python codebase into .kit memory")
    parser.add_argument("path", help="Root directory of the project")
    args = parser.parse_args()
    
    ingestor = CodebaseIngestor(args.path)
    ingestor.scan()
    print("\n✅ Ingestion Complete. Your brain is now indexed.")

if __name__ == "__main__":
    main()
