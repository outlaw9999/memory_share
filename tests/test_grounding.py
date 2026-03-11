"""
Test Layer 1: Query Grounding
Tests the pipeline: natural language → keywords → symbols → ranked candidates

Target: < 10ms latency, > 95% accuracy
"""

import pytest
from dataclasses import dataclass
from typing import List


# ============== MODELS (Mirror kit/core/grounding.py) ==============

@dataclass
class GroundedQuery:
    """Output from query grounding pipeline"""
    raw: str
    intent: str  # "DEBUG" | "ARCHITECTURE" | "DECISION" | "GENERAL"
    symbols: List[str]
    confidence: float


# ============== HELPERS (Temporary - will be replaced by real implementation) ==============

def classify_intent(query: str) -> str:
    """Classify query intent using heuristics"""
    q_lower = query.lower()
    
    if any(w in q_lower for w in ["call", "depend", "import", "architecture"]):
        return "ARCHITECTURE"
    elif any(w in q_lower for w in ["fail", "bug", "error", "wrong"]):
        return "DEBUG"
    elif any(w in q_lower for w in ["why", "chose", "decision", "design"]):
        return "DECISION"
    else:
        return "GENERAL"


def extract_keywords(query: str) -> List[str]:
    """Extract keywords from query"""
    stopwords = {"why", "does", "the", "a", "an", "do", "is", "are", "have", "how", "what"}
    tokens = query.lower().split()
    return [t for t in tokens if t not in stopwords and len(t) > 2]


# ============== TESTS ==============

class TestIntentClassification:
    """Tests for _classify_intent function"""
    
    def test_debug_intent(self):
        """Should recognize DEBUG intent from keywords"""
        assert classify_intent("Why does login fail?") == "DEBUG"
        assert classify_intent("What's wrong with authentication?") == "DEBUG"
        assert classify_intent("Error in token verification") == "DEBUG"
    
    def test_architecture_intent(self):
        """Should recognize ARCHITECTURE intent"""
        assert classify_intent("How does auth depend on utils?") == "ARCHITECTURE"
        assert classify_intent("What calls login function?") == "ARCHITECTURE"
        assert classify_intent("Import relationships in billing") == "ARCHITECTURE"
    
    def test_decision_intent(self):
        """Should recognize DECISION intent"""
        assert classify_intent("Why did we choose SHA-256?") == "DECISION"
        assert classify_intent("Design decision for JWT tokens") == "DECISION"
    
    def test_general_intent(self):
        """Should default to GENERAL for unrecognized queries"""
        assert classify_intent("foo bar baz") == "GENERAL"
        assert classify_intent("xyz123456") == "GENERAL"


class TestKeywordExtraction:
    """Tests for _extract_keywords function"""
    
    def test_removes_stopwords(self):
        """Should filter out stopwords"""
        keywords = extract_keywords("Why does login fail?")
        assert "why" not in keywords
        assert "does" not in keywords
        assert "login" in keywords
        assert "fail" in keywords
    
    def test_case_insensitive(self):
        """Should convert to lowercase"""
        keywords = extract_keywords("Login Function")
        assert "login" in keywords
        assert "function" in keywords
    
    def test_min_length_filter(self):
        """Should filter tokens < 3 chars"""
        keywords = extract_keywords("Why is auth so slow?")
        assert "is" not in keywords  # 2 chars
        assert "auth" in keywords    # 4 chars
        assert "slow" in keywords    # 4 chars
    
    def test_empty_query(self):
        """Should handle empty query gracefully"""
        keywords = extract_keywords("why the a an")
        assert len(keywords) == 0


class TestSymbolRanking:
    """Tests for rank_symbols function"""
    
    def test_exact_match_ranks_highest(self):
        """Exact match should rank first despite lower FTS score"""
        # TODO: Test data structure
        # Simulate FTS results: login_handler(0.8), login(0.3), do_login(0.9)
        # Expected: login should rank first due to exact match
        pass
    
    def test_suffix_match_ranks_second(self):
        """Suffix match (e.g., login_handler) should rank high"""
        pass
    
    def test_fts_score_used_as_tiebreaker(self):
        """When no exact/suffix match, use FTS BM25 score"""
        pass
    
    def test_top_n_results(self):
        """Should return only top-N symbols"""
        # Expect: top 5 symbols by score
        pass


class TestGroundQueryFullPipeline:
    """Integration tests for full ground_query pipeline"""
    
    def test_ground_query_with_matching_symbol(self, mock_atlas_db):
        """Should ground query and find matching symbol"""
        # TODO: Call ground_query("Why does login fail?", mock_atlas_db)
        # Expected: GroundedQuery(
        #    intent="DEBUG",
        #    symbols=["login"],
        #    confidence=1.0
        # )
        pass
    
    def test_ground_query_no_symbols_found(self, mock_atlas_db):
        """Should ground query even if no symbols match"""
        # TODO: Call ground_query("foo bar baz xyz", mock_atlas_db)
        # Expected: GroundedQuery(
        #    intent="GENERAL",
        #    symbols=[],
        #    confidence=0.6  # low confidence when no symbols found
        # )
        pass
    
    def test_ground_query_multiple_symbols(self, mock_atlas_db):
        """Should handle queries that resolve to multiple symbols"""
        # TODO: Verify ranking order
        pass
    
    def test_ground_query_latency(self, mock_atlas_db):
        """Total latency should be < 10ms"""
        pass


class TestEdgeCases:
    """Edge cases for query grounding"""
    
    def test_unicode_query(self):
        """Should handle unicode characters"""
        result = classify_intent("Tại sao login lại thất bại?")
        assert isinstance(result, str)
    
    def test_very_long_query(self):
        """Should handle long queries"""
        long_query = " ".join(["word"] * 1000)
        keywords = extract_keywords(long_query)
        assert "word" in keywords
    
    def test_symbols_with_special_chars(self, mock_atlas_db):
        """Should handle symbols with underscores, numbers"""
        # e.g., login_v2, process_payment_3
        pass


# ============== PERFORMANCE BASELINE ==============

class TestPerformanceBaseline:
    """Performance targets from ARCHITECTURE.md"""
    
    def test_intent_detection_under_1ms(self):
        """_classify_intent must complete in < 1ms"""
        import time
        start = time.perf_counter()
        for _ in range(100):
            classify_intent("Why does login fail?")
        elapsed = (time.perf_counter() - start) / 100
        assert elapsed < 0.001  # 1ms
    
    def test_keyword_extraction_under_1ms(self):
        """_extract_keywords must complete in < 1ms"""
        import time
        start = time.perf_counter()
        for _ in range(100):
            extract_keywords("Why does login fail?")
        elapsed = (time.perf_counter() - start) / 100
        assert elapsed < 0.001
    
    def test_total_grounding_under_10ms(self, mock_atlas_db):
        """Full grounding pipeline must complete in < 10ms"""
        # TODO: Run ground_query 100 times and verify P95 < 10ms
        pass
