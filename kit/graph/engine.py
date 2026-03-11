import sqlite3
from typing import Set, Tuple, List, Dict
from kit.schema import TraversalPlan, SubgraphContext
from kit.core.graph_store import GraphStore

class GraphEngine:
    def __init__(self, store: GraphStore):
        """
        Khởi tạo với GraphStore. 
        Thực thi Batched BFS Traversal Plan với Canonicalization.
        """
        self.store = store
        self.conn = store.conn

    def execute(self, plan: TraversalPlan) -> SubgraphContext:
        cur = self.conn.cursor()
        
        if not plan.entry_symbols:
            return SubgraphContext(nodes=[], edges=[], layer_sources=plan.layers)

        # 1. Start with Entry IDs directly
        placeholders = ','.join(['?'] * len(plan.entry_symbols))
        query = f"""
            SELECT id, fqn 
            FROM symbols
            WHERE id IN ({placeholders})
        """
        cur.execute(query, plan.entry_symbols)
        
        start_nodes = cur.fetchall()
        if not start_nodes:
            return SubgraphContext(nodes=[], edges=[], layer_sources=plan.layers)
            
        visited_ids = set()
        frontier = set()
        node_map = {}
        
        # Lấy duy nhất 1 node ID cao nhất cho mỗi FQN để tránh lặp
        for row in start_nodes:
            node_id = row['id']
            fqn = row['fqn']
            if node_id not in visited_ids:
                visited_ids.add(node_id)
                frontier.add(node_id)
                node_map[node_id] = fqn
            
        all_edges = []
        
        # 2. BATCHED BFS: Duyệt tuần tự theo tầng
        for depth in range(plan.max_depth):
            if not frontier: 
                break
                
            frontier_list = list(frontier)
            
            # Chỉ tốn 1 QUERY cho CẢ MỘT TẦNG BFS!
            placeholders = ','.join(['?'] * len(frontier_list))
            layer_placeholders = ','.join(['?'] * len(plan.layers))
            
            # Quét các cạnh đi ra (forward traverse)
            sql = f"""
                SELECT source_id, layer, target_alias
                FROM edges e
                WHERE e.source_id IN ({placeholders}) 
                AND e.layer IN ({layer_placeholders})
            """
            
            params = frontier_list + plan.layers
            
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                break # Fallback nếu schema error
            
            next_frontier = set()
            for row in rows:
                source_id = row['source_id']
                target_alias = row['target_alias']
                layer = row['layer']
                
                # LATE BINDING: Tra cứu ngay ID chuẩn của nó
                target_id = self.store.resolve_alias(target_alias)
                if not target_id:
                    continue
                    
                cur.execute("SELECT fqn FROM symbols WHERE id=?", (target_id,))
                fqn_row = cur.fetchone()
                if not fqn_row:
                    continue
                    
                target_fqn = fqn_row['fqn']
                
                # Lưu cạnh với format (Node1 -> Layer -> Node2)
                all_edges.append({
                    "source": node_map.get(source_id, f"Node_{source_id}"),
                    "target": target_fqn,
                    "layer": layer
                })
                
                # Thêm neighbor vào hàng đợi nếu chưa thăm
                if target_id not in visited_ids:
                    visited_ids.add(target_id)
                    node_map[target_id] = target_fqn
                    next_frontier.add(target_id)
            
            frontier = next_frontier

        return SubgraphContext(
            nodes=[{"id": name} for name in node_map.values()],
            edges=all_edges,
            layer_sources=plan.layers
        )
