from typing import Any


class ContextBuilder:
    """
    Context Pruning and Simplification.
    Chưng cất các cạnh Subgraph phức tạp thành Atomic Facts.
    """

    RELATIONS = {0: "calls", 1: "asserts", 2: "causes", 3: "fixes"}

    def build(self, subgraph: Any) -> str:
        lines = []

        for edge in subgraph.edges:
            source = edge.get("source", str(edge.get("source_id")))
            target = edge.get("target", str(edge.get("target_id")))
            layer = edge.get("layer", 0)

            relation = self.RELATIONS.get(layer, "relates")
            lines.append(f"{source} -> {relation} -> {target}")

        return "\n".join(lines[:50])
