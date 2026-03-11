import time
from typing import Dict
from kit.core.graph_store import GraphStore

class GraphRankEngine:
    """
    V1.2 Architectural Brain: Importance Ranking Engine
    Uses PageRank-inspired algorithm to identify critical code components.
    """
    def __init__(self, store: GraphStore):
        self.store = store

    def compute_importance(self, iterations: int = 20, damping_factor: float = 0.85):
        """
        Tính toán điểm số quan trọng (PageRank) cho toàn bộ symbol trong graph.
        """
        print(f"[*] Starting Importance Ranking calculation ({iterations} iterations)...")
        start_time = time.time()
        
        cur = self.store.conn.cursor()
        
        # 1. Lấy danh sách tất cả Symbol IDs
        cur.execute("SELECT id FROM symbols")
        symbol_ids = [row[0] for row in cur.fetchall()]
        if not symbol_ids:
            return {}
            
        num_symbols = len(symbol_ids)
        # Khởi tạo điểm số ban đầu: 1 / N
        ranks = {s_id: 1.0 / num_symbols for s_id in symbol_ids}
        
        # 2. Lấy danh sách cạnh (edges) và resolve target_alias -> target_id
        # Lưu ý: Cạnh trong .kit V1.1 lưu target_alias, ta cần resolve để tính PageRank
        cur.execute("SELECT source_id, target_alias FROM edges")
        raw_edges = cur.fetchall()
        
        # Build adjacency list: target -> list of sources (who calls me)
        # And out-degree count: source -> count
        incoming_links = {s_id: [] for s_id in symbol_ids}
        out_degrees = {s_id: 0 for s_id in symbol_ids}
        
        # Cache alias resolution to speed up iterations
        alias_to_id = {}
        
        print(f"[*] Resolving {len(raw_edges)} edges for graph topology...")
        for source_id, target_alias in raw_edges:
            if target_alias not in alias_to_id:
                target_id = self.store.resolve_alias(target_alias)
                alias_to_id[target_alias] = target_id
            
            target_id = alias_to_id[target_alias]
            if target_id and target_id in symbol_ids:
                incoming_links[target_id].append(source_id)
                out_degrees[source_id] += 1

        # 3. Iterative PageRank calculation
        for i in range(iterations):
            new_ranks = {}
            # Tính phần điểm số bị rò rỉ từ các node không có link đi (dangling nodes)
            # Trong PageRank chuẩn, điểm này được chia đều cho tất cả các node.
            # Ở đây ta tối ưu hóa bằng cách dùng damping factor.
            
            for symbol_id in symbol_ids:
                rank_sum = 0
                for source_id in incoming_links[symbol_id]:
                    # Điểm đóng góp = rank(source) / out_degree(source)
                    rank_sum += ranks[source_id] / out_degrees[source_id]
                
                # Formula: PR(A) = (1-d)/N + d * sum(PR(In)/Out(In))
                new_ranks[symbol_id] = (1 - damping_factor) / num_symbols + damping_factor * rank_sum
            
            ranks = new_ranks
            if i % 5 == 0:
                print(f"  [.] Iteration {i} complete...")

        duration = time.time() - start_time
        print(f"[OK] Importance scores calculated in {duration:.2f}s.")
        return ranks

    def update_database(self, ranks: Dict[int, float]):
        """Lưu điểm số vào database."""
        print(f"[*] Syncing {len(ranks)} importance scores to database...")
        self.store.update_importance_scores(ranks)
        print("[OK] Database updated.")

    def get_hotspots(self, limit: int = 10):
        """Lấy danh sách các symbols quan trọng nhất."""
        cur = self.store.conn.cursor()
        cur.execute("""
            SELECT fqn, kind, importance_score 
            FROM symbols 
            ORDER BY importance_score DESC 
            LIMIT ?
        """, (limit,))
        return cur.fetchall()
