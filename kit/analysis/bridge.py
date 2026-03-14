# kit/analysis/bridge.py
import re
from pathlib import Path
from typing import Any

from kit.core.graph_store import GraphStore
from kit.fs.walker import safe_walk


# Regex "sát thủ" để nhận diện Symbol trong văn bản
# Matches CamelCase terms (at least two words combined) or `code_snippets`
SYMBOL_PATTERN = re.compile(r"(\b[A-Z][a-zA-Z0-9]{3,}\b|`([a-zA-Z0-9_]+)`)")


class SemanticBridge:
    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def run(self, root_path: str) -> None:
        """Index all markdown files in the root_path and bridge them to code symbols."""
        print(f"[*] Starting Semantic Bridge on {root_path}...")
        count = 0
        for doc_path in safe_walk(root_path):
            if doc_path.suffix == ".md":
                self.index_document(doc_path)
                count += 1
        print(f"[OK] Semantic Bridge complete. Indexed {count} documents.")

    def index_document(self, path: Path) -> None:
        try:
            content = path.read_text(errors="ignore")
        except Exception as e:
            print(f"  [!] Failed to read {path}: {e}")
            return

        # Create Document node
        doc_id = self.store.create_document_node(path)

        # Simple sentence splitter (can be improved)
        sentences = [s.strip() for s in content.split(".") if s.strip()]

        for sentence in sentences:
            # Look for symbols within the sentence
            matches = SYMBOL_PATTERN.findall(sentence)

            for match in matches:
                # Extract symbol (handle both groups)
                symbol = match[0] or match[1]
                if not symbol:
                    continue

                # Check if symbol exists in graph
                symbol_id = self.store.find_symbol_by_alias(symbol)
                if symbol_id:
                    # Create assertion (Layer 2)
                    self.store.create_assertion(doc_id, sentence, confidence=0.7)
