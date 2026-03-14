import re
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple


class ASTMarkdownParser:
    """
    Antigravity AST-lite Parser (The "Lean Surgeon").
    Identifies knowledge nodes via stable anchors: <!-- node:id=... -->
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = self._load_file()
        self.node_regex = r"<!--\s*node:id=([\w-]+)\s*-->"

    def _load_file(self) -> str:
        if not self.file_path.exists():
            return ""
        return self.file_path.read_text(encoding="utf-8")

    def get_hash(self) -> str:
        """Returns SHA256 of current content for OCC check."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def _get_node_range(self, node_id: str) -> Tuple[int, int]:
        """Finds the line boundaries of a node based on its ID anchor."""
        lines = self.content.splitlines()
        start_idx = -1
        anchor = f"node:id={node_id}"

        for i, line in enumerate(lines):
            if anchor in line:
                start_idx = i
                break

        if start_idx == -1:
            return (-1, -1)

        # Node ends when the next node anchor is found or at EOF
        end_idx = len(lines)
        for i in range(start_idx + 1, len(lines)):
            if re.search(self.node_regex, lines[i]):
                end_idx = i
                break
        return start_idx, end_idx

    def update_node(self, node_id: str, new_body: str) -> bool:
        """Updates Node content while preserving the anchor and its title."""
        start, end = self._get_node_range(node_id)
        if start == -1:
            return False

        lines = self.content.splitlines()
        # Preserve the anchor/header line (the first line of the node block)
        anchor_line = lines[start]

        # Build the new block: Anchor + New Body
        new_block = [anchor_line] + new_body.strip().splitlines()

        lines[start:end] = new_block
        self.content = "\n".join(lines)
        return True

    def append_node(self, node_id: str, title: str, content: str) -> None:
        """Appends a new knowledge node with a stable anchor to the document."""
        anchor = f"<!-- node:id={node_id} -->"
        new_node = f"\n\n{anchor}\n## {title}\n\n{content}\n"
        self.content = self.content.strip() + new_node

    def delete_node(self, node_id: str) -> bool:
        """Deletes a knowledge node completely."""
        start, end = self._get_node_range(node_id)
        if start == -1:
            return False
        lines = self.content.splitlines()
        del lines[start:end]
        self.content = "\n".join(lines)
        return True

    def commit(self, shadow_path: Optional[Path] = None) -> None:
        """Atomic write via Shadow Paging / Atomic Replace."""
        path = shadow_path or self.file_path
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic rename implementation
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(self.content, encoding="utf-8")
        import os

        os.replace(tmp_path, path)
