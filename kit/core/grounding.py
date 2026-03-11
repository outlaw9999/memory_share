import re
from typing import List
from kit.schema import GroundedQuery

class GroundingEngine:
    """
    Hạt nhân định vị: Biến Ngôn ngữ tự nhiên -> Danh sách Symbols thực tế.
    Tốc độ mục tiêu: < 10ms trên 1 triệu symbols.
    Đã được tối ưu để dùng persistent conn thay vì db_path.
    """
    
    STOPWORDS = {
        "why", "does", "the", "a", "an", "is", "are", "do", "how", "what", 
        "where", "did", "we", "can", "to", "in", "of", "for", "with"
    }

    # Trọng số loại symbol để khử nhiễu (Disambiguation)
    KIND_WEIGHTS = {
        "function": 1.0,
        "class": 0.8,
        "method": 0.9,
        "module": 0.5,
        "variable": 0.3
    }

    def __init__(self, conn):
        self.conn = conn

    def detect_intent(self, query: str) -> str:
        """Phân loại ý định bằng Heuristics tốc độ cao."""
        q = query.lower()
        if any(w in q for w in ["fail", "error", "bug", "wrong", "fix", "issue", "crash"]):
            return "DEBUG"
        if any(w in q for w in ["depend", "call", "import", "architecture", "structure", "layer"]):
            return "ARCHITECTURE"
        if any(w in q for w in ["why", "design", "decision", "chose", "history", "rationale"]):
            return "DECISION"
        return "GENERAL"

    def extract_keywords(self, query: str) -> List[str]:
        """Trích xuất danh từ riêng và từ khóa code."""
        # Loại bỏ ký tự đặc biệt, giữ lại alphanumeric và dấu gạch dưới
        clean = re.sub(r'[^a-zA-Z0-9_ ]', ' ', query)
        tokens = clean.split()
        return [
            t for t in tokens 
            if t.lower() not in self.STOPWORDS and len(t) > 2
        ]

    def rank_symbols(self, keyword: str, candidates: List[dict]) -> List[int]:
        """
        Thuật toán xếp hạng đa tầng:
        Score = Exact(1.0) + Suffix(0.6) + KindWeight(0.1) + FTS_Rank(0.2)
        """
        scored_results = []
        kw_lower = keyword.lower()

        for r in candidates:
            row = dict(r)
            item_id = row['id']
            name = row['name']
            name_lower = name.lower()
            kind = row.get('kind', 'function')
            
            # FTS rank bm25 from user suggestion
            score = row.get('score', 0.1)
            
            # Khớp chính xác
            if name_lower == kw_lower:
                score += 1.0
            
            # Khớp hậu tố
            elif name_lower.endswith(f"_{kw_lower}") or name_lower.endswith(kw_lower):
                score += 0.6
            
            # Trọng số loại symbol
            score += self.KIND_WEIGHTS.get(kind, 0.1) * 0.2

            scored_results.append((item_id, score))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored_results]

    def resolve(self, query: str) -> GroundedQuery:
        """Luồng xử lý chính: NL -> GroundedQuery."""
        intent = self.detect_intent(query)
        keywords = self.extract_keywords(query)
        
        final_symbols = []
        
        cur = self.conn.cursor()
        for kw in keywords:
            # V1: Alias-first lookup. FTS5 strategy would require building FTS over aliases, 
            # so for V1 we do exact/LIKE matches on normalized aliases which is extremely fast.
            kw_lower = kw.lower()
            query_sql = """
                SELECT s.id as id, s.fqn as name, s.kind, a.confidence as score
                FROM symbol_aliases a
                JOIN symbols AS s ON s.id = a.symbol_id
                WHERE a.normalized_alias LIKE ?
                ORDER BY a.confidence DESC
                LIMIT 20
            """
            try:
                cur.execute(query_sql, (f"%{kw_lower}%",))
                rows = cur.fetchall()
                if rows:
                    ranked = self.rank_symbols(kw, rows)
                    final_symbols.extend(ranked[:3])
            except Exception as e:
                pass

        unique_symbols = list(dict.fromkeys(final_symbols))
        
        confidence = 1.0 if unique_symbols else 0.4
        if intent == "GENERAL" and not unique_symbols:
            confidence = 0.2

        return GroundedQuery(
            original_query=query,          # Following kit.schema
            intents=[intent],              # Following kit.schema
            symbols=unique_symbols[:10],   # Limiting noise
            confidence=confidence
        )
