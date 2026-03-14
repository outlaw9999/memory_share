import time
from typing import Any, Dict, List, Optional

from kit.core.graph_store import GraphStore


class GraphRankEngine:
    """
    V1.2 Architectural Brain: Importance Ranking Engine
    Uses PageRank-inspired algorithm to identify critical code components.
    """

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def compute_importance(
        self, iterations: int = 20, damping_factor: float = 0.85
    ) -> Dict[int, float]:
        """
        Tính toán điểm số quan trọng (PageRank) cho toàn bộ symbol trong graph.
        """
        print(
            f"[*] Starting Importance Ranking calculation ({iterations} iterations)..."
        )
        start_time = time.time()

        cur = self.store.conn.cursor()

        # 1. Lấy danh sách tất cả Symbol IDs
        cur.execute("SELECT id FROM symbols")
        symbol_ids: List[int] = [row[0] for row in cur.fetchall()]
        if not symbol_ids:
            return {}

        num_symbols = len(symbol_ids)
        # Khởi tạo điểm số ban đầu: 1 / N
        ranks: Dict[int, float] = {s_id: 1.0 / num_symbols for s_id in symbol_ids}

        # 2. Lấy danh sách cạnh (edges) từ Layer 1 (Structural)
        # Điều này ngăn Semantic layer phá ranking (PageRank Isolation)
        cur.execute("SELECT source_id, target_alias FROM edges WHERE layer = 1")
        raw_edges = cur.fetchall()

        # Build adjacency list: target -> list of sources (who calls me)
        # And out-degree count: source -> count
        incoming_links: Dict[int, List[int]] = {s_id: [] for s_id in symbol_ids}
        out_degrees: Dict[int, int] = {s_id: 0 for s_id in symbol_ids}

        # Cache alias resolution to speed up iterations
        alias_to_id: Dict[str, Optional[int]] = {}

        print(f"[*] Resolving {len(raw_edges)} edges for graph topology...")
        for source_id, target_alias in raw_edges:
            if target_alias not in alias_to_id:
                target_id = self.store.resolve_alias(target_alias)
                alias_to_id[target_alias] = target_id

            target_id = alias_to_id[target_alias]
            if target_id is not None and target_id in incoming_links:
                incoming_links[target_id].append(source_id)
                out_degrees[source_id] += 1

        print(f"[*] Running PageRank for {iterations} iterations...")

        # 3. PageRank iterations
        for i in range(iterations):
            new_ranks: Dict[int, float] = {}

            for s_id in symbol_ids:
                # Teleport contribution
                rank = (1 - damping_factor) / num_symbols

                # Sum incoming contributions
                for source_id in incoming_links[s_id]:
                    if out_degrees[source_id] > 0:
                        rank += (
                            damping_factor * ranks[source_id] / out_degrees[source_id]
                        )

                new_ranks[s_id] = rank

            ranks = new_ranks

            if i % 5 == 0:
                print(f"  - Iteration {i + 1}/{iterations} complete")

        elapsed = time.time() - start_time
        print(f"[*] Importance ranking complete in {elapsed:.2f}s")

        # Update graph store
        self.store.update_importance_scores(ranks)

        return ranks
