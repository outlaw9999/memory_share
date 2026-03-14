# kit/query/reasoning.py
from pathlib import Path
from typing import Any, Dict, List, Optional

from kit.core.graph_store import GraphStore

from kit.llm.client import LLMClient


class ReasoningEngine:
    def __init__(
        self, store: GraphStore, llm_client: Optional[LLMClient] = None
    ) -> None:
        self.store = store
        self.llm = llm_client

    def why(self, symbol_name: str, offline: bool = False) -> str:
        """Explain the architectural and semantic importance of a symbol (Human readable)."""
        facts = self.get_symbol_facts(symbol_name)
        if "error" in facts:
            return str(facts["error"])

        # Logic Fallback / Priority for LLM
        if not (offline or not self.llm):
            try:
                return self.llm.summarize_facts(facts)
            except Exception as e:
                # Fallback to deterministic report
                return f"--- LLM Unavailable ({e}) ---\n{self._format_deterministic_report(facts)}"

        return self._format_deterministic_report(facts)

    def get_symbol_facts(self, symbol_name: str) -> Dict[str, Any]:
        """Gather all deterministic facts about a symbol."""
        symbol_id = self.store.find_symbol_by_alias(symbol_name)
        if not symbol_id:
            return {"error": f"[!] Symbol '{symbol_name}' not found in graph."}

        return self._get_context_facts(symbol_id)

    def _get_context_facts(self, symbol_id: int) -> Dict[str, Any]:
        cur = self.store.conn.cursor()
        cur.execute(
            "SELECT fqn, importance_score FROM symbols WHERE id=?", (symbol_id,)
        )
        row = cur.fetchone()
        if row is None:
            return {"error": f"Symbol ID {symbol_id} not found"}
        fqn, score = row

        callers = self.store.find_callers(fqn, limit=5)

        # Find assertions
        q = """
        SELECT a.raw_text, d.fqn 
        FROM edges e
        JOIN assertions a ON e.source_id = a.node_id
        JOIN symbols d ON a.doc_id = d.id
        JOIN symbols s ON s.id = ?
        WHERE (e.target_alias = s.fqn OR e.target_alias = ?) AND e.layer = 2
        """
        short_name = fqn.split(".")[-1]
        cur.execute(q, (symbol_id, short_name.lower()))
        assertions = [
            {"text": text, "doc": Path(doc_fqn).name}
            for text, doc_fqn in cur.fetchall()
        ]

        return {
            "name": fqn,
            "rank": score,
            "callers": [c.caller for c in callers],
            "assertions": assertions,
        }

    def _format_deterministic_report(self, facts: Dict[str, Any]) -> str:
        """Standard architectural report based on graph data."""
        report: List[str] = [f"--- DETERMINISTIC REPORT: {facts['name']} ---"]
        report.append(f"Importance Score: {facts['rank']:.4f}")

        report.append("\n[Structural Logic]")
        if facts["callers"]:
            for caller in facts["callers"]:
                report.append(f"  <- Called by {caller}")
        else:
            report.append(
                "  - No incoming calls detected (potential entry point or utility)."
            )

        report.append("\n[Semantic Intent]")
        if facts["assertions"]:
            for assertion in facts["assertions"]:
                report.append(f'  - "{assertion["text"]}" (Source: {assertion["doc"]})')
        else:
            report.append("  - No documentation assertions found for this symbol.")

        return "\n".join(report)
