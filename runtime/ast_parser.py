import json
import hashlib
from typing import Dict, Any, Tuple

class MarkdownASTDriver:
    """
    Simulates AST-based operations on Markdown files.
    Allows agents to mutate specific {#node_id} / <!-- id: node --> instead of raw text replacement.
    This eliminates cognitive race conditions like renaming headers breaking agent logic.
    """
    
    @staticmethod
    def calculate_hash(content: str) -> str:
        """Tính toán Hash để kiểm tra xem file có thay đổi từ lúc Agent đọc không."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def identify_node(self, file_content: str, node_id: str) -> bool:
        """Verify the node exists in the AST."""
        # Note: A real implementation would parse the Markdown DOM (e.g., mistune AST)
        # Here we use the standard Antigravity anchor format <!-- id: node_id -->
        marker = f"<!-- id: {node_id} -->"
        return marker in file_content

    def mutate_node(self, file_content: str, node_id: str, operation: str, new_content: str) -> str:
        """
        Applies a semantic AST mutation cleanly.
        Supported Ops: 
            - append_child: Adds content right after the node anchor.
            - replace: Replaces the block immediately following the anchor.
        """
        marker = f"<!-- id: {node_id} -->"
        if marker not in file_content:
            raise ValueError(f"AST Error: Node '{node_id}' not found in Document Model.")
            
        parts = file_content.split(marker)
        
        # AST Mutation Logic proxy
        if operation == "append_child":
            return parts[0] + marker + "\n" + new_content + "\n" + parts[1]
        elif operation == "replace":
            # Very naive replace for prototype purpose. 
            # Real parser would extract the boundary of the `Heading` node and replace its siblings until next header.
            return parts[0] + marker + "\n" + new_content + "\n"
        else:
            raise ValueError(f"AST Error: Unsupported mutation operation '{operation}'")
