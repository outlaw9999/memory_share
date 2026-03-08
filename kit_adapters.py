import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(os.environ.get("ANTIGRAVITY_WORKSPACE_ROOT", os.path.dirname(os.path.abspath(__file__))))

sys.path.append(str(WORKSPACE_ROOT))
from plugins.atlas_indexer.graph_store import GraphStore

sys.path.append(str(WORKSPACE_ROOT / "brain" / "ops"))
try:
    import query_layer3
except ImportError:
    query_layer3 = None


class AtlasAdapter:
    """Adapter for searching and reading code context from ATLAS.
    
    PHASE 8: CONTEXT ENGINE (FROZEN)
    ================================
    
    This class implements the frozen Phase 8 contract for code context retrieval.
    
    Stable CLI commands:
    - kit symbol <q>        → definition() returns code_symbol JSON
    - kit context <symbol>  → get_unified_context() returns code_context JSON
    - kit callers <symbol>  → callers() returns list[code_caller]
    - kit snippet <path>    → snippet() returns code_snippet
    
    JSON fields are locked:
    - code_symbol: {type, name, kind, path, line, rank}
    - code_context: {type, symbol, definition, callers, callees, snippet, metrics, docs}
    
    These contracts MUST NOT change. JSON structure serves Agent tool schema.
    
    Phase 9 (Graph Exploration) adds only new methods without modifying Phase 8 outputs.
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.store = GraphStore(workspace_root / ".antigravity" / "atlas" / "atlas.db")

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        results = []
        for symbol in self.store.search_symbols(query, limit=limit, fuzzy=True):
            results.append(
                {
                    "type": "code_symbol",
                    "name": symbol.name,
                    "kind": symbol.kind,
                    "path": symbol.file,
                    "line": symbol.line,
                    "rank": 1.0,
                }
            )
        return results

    def definition(self, query: str) -> Optional[Dict[str, Any]]:
        # Phase 10: Support file-qualified lookup syntax "file::symbol"
        if "::" in query:
            return self._definition_file_qualified(query)
        
        # Phase 9 fallback: name-based lookup
        candidates = self.store.search_symbols(query, limit=10, fuzzy=False)
        if not candidates:
            candidates = self.store.search_symbols(query, limit=10, fuzzy=True)
        if not candidates:
            return None

        ranked = self._rank_symbols(candidates, query)
        symbol = ranked[0]
        return {
            "type": "code_symbol",
            "name": symbol.name,
            "kind": symbol.kind,
            "path": symbol.file,
            "line": symbol.line,
            "rank": 1.0 if symbol.name == query else 0.9,
        }

    def _definition_file_qualified(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Phase 10: Resolve file-qualified symbol reference.
        
        Syntax: "relative/path/file.py::symbol_name"
        Returns: Symbol definition from that specific file
        """
        parts = query.split("::", 1)
        if len(parts) != 2:
            return None
        
        file_query, symbol_name = parts
        
        # Normalize file path to match stored paths
        # Support both relative and absolute paths
        file_query = file_query.replace("\\", "/")
        
        # Search all symbols to find file-qualified match
        all_symbols = self.store.list_symbols()
        
        for symbol in all_symbols:
            # Normalize stored path for comparison
            stored_path = symbol.file.replace("\\", "/")
            
            # Match if filename matches or full path matches
            if stored_path.endswith(file_query) or stored_path == file_query:
                if symbol.name == symbol_name:
                    return {
                        "type": "code_symbol",
                        "name": symbol.name,
                        "kind": symbol.kind,
                        "path": symbol.file,
                        "line": symbol.line,
                        "rank": 1.0,
                    }
        
        return None

    def _rank_symbols(self, symbols: List[Any], query: str) -> List[Any]:
        return sorted(
            symbols,
            key=lambda symbol: (
                symbol.name != query,
                not symbol.name.startswith(query),
                self._is_test_path(symbol.file),
                len(Path(symbol.file).parts),
                len(symbol.file),
                len(symbol.name),
                symbol.file,
                symbol.line,
            ),
        )

    def _is_test_path(self, path: str) -> bool:
        normalized = path.replace("\\", "/").lower()
        file_name = Path(path).name.lower()
        return (
            "/test/" in normalized
            or "/tests/" in normalized
            or file_name.startswith("test_")
            or file_name.endswith("_test.py")
        )

    def callers(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        for call in self.store.find_callers(symbol, limit=limit):
            results.append(
                {
                    "type": "code_caller",
                    "caller": call.caller,
                    "callee": call.callee,
                    "path": call.file,
                    "line": call.line,
                    "rank": 1.0,
                }
            )
        return results

    def callees(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        for call in self.store.find_callees(symbol, limit=limit):
            results.append(
                {
                    "type": "code_callee",
                    "caller": call.caller,
                    "callee": call.callee,
                    "path": call.file,
                    "line": call.line,
                    "rank": 1.0,
                }
            )
        return results

    def snippet(self, target: str, radius: int = 10) -> Dict[str, Any]:
        path_part, _, line_part = target.rpartition(":")
        if not path_part or not line_part:
            raise ValueError("snippet target must be PATH:LINE")

        file_path = Path(path_part)
        if not file_path.is_absolute():
            file_path = self.workspace_root / file_path

        line_number = int(line_part)
        lines = file_path.read_text(encoding="utf-8").splitlines()
        start = max(1, line_number - radius)
        end = min(len(lines), line_number + radius)
        return {
            "type": "code_snippet",
            "path": str(file_path),
            "line": line_number,
            "start_line": start,
            "end_line": end,
            "snippet": "\n".join(lines[start - 1 : end]),
        }

    def get_unified_context(
        self,
        symbol: str,
        *,
        caller_limit: int = 5,
        callee_limit: int = 5,
        snippet_radius: int = 8,
    ) -> Dict[str, Any]:
        definition = self.definition(symbol)
        callers = self.callers(symbol, limit=caller_limit)
        callees = self.callees(symbol, limit=callee_limit)
        snippet = None
        if definition is not None:
            snippet = self.snippet(f"{definition['path']}:{definition['line']}", radius=snippet_radius)

        return {
            "type": "code_context",
            "symbol": symbol,
            "definition": definition,
            "callers": callers,
            "callees": callees,
            "snippet": snippet,
            "metrics": {
                "caller_count": len(callers),
                "callee_count": len(callees),
                "has_definition": definition is not None,
            },
        }

    def get_related_info(
        self,
        symbol: str,
        *,
        similar_limit: int = 5,
        caller_limit: int = 5,
        callee_limit: int = 5,
        module_limit: int = 8,
    ) -> Dict[str, Any]:
        definition = self.definition(symbol)
        callers = self.callers(symbol, limit=caller_limit)
        callees = self.callees(symbol, limit=callee_limit)
        similar = self._similar_symbols(symbol, limit=similar_limit)
        module_peers: List[Dict[str, Any]] = []
        if definition is not None:
            module_peers = self._module_peers(definition["path"], definition["name"], limit=module_limit)

        return {
            "type": "code_related",
            "symbol": symbol,
            "definition": definition,
            "related": {
                "similar": similar,
                "callers": callers,
                "callees": callees,
                "module_peers": module_peers,
            },
            "metrics": {
                "similar_count": len(similar),
                "caller_count": len(callers),
                "callee_count": len(callees),
                "module_peer_count": len(module_peers),
                "has_definition": definition is not None,
            },
        }

    def _similar_symbols(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        family_query = self._family_query(symbol)
        results = []
        seen = set()
        for item in self.store.search_related_symbols(
            family_query,
            exclude_name=symbol,
            limit=max(limit * 4, 10),
        ):
            if item["name"] in seen or self._is_test_path(str(item["file"])):
                continue
            seen.add(str(item["name"]))
            results.append(
                {
                    "type": "code_symbol",
                    "name": item["name"],
                    "kind": item["kind"],
                    "path": item["file"],
                    "line": item["line"],
                    "rank": 1.0,
                    "fts_rank": item["fts_rank"],
                    "degree": item["degree"],
                }
            )
            if len(results) >= limit:
                break
        return results

    def _family_query(self, symbol: str) -> str:
        tokens = [token for token in re.split(r"[^0-9A-Za-z_]+|_", symbol) if token]
        if tokens:
            return max(enumerate(tokens), key=lambda item: (len(item[1]), item[0]))[1]
        return symbol

    def _module_peers(self, path: str, symbol_name: str, limit: int) -> List[Dict[str, Any]]:
        peers = []
        for item in self.store.list_symbols(path):
            if item.name == symbol_name:
                continue
            peers.append(
                {
                    "type": "code_symbol",
                    "name": item.name,
                    "kind": item.kind,
                    "path": item.file,
                    "line": item.line,
                    "rank": 1.0,
                }
            )
        peers.sort(key=lambda item: (self._is_test_path(item["path"]), item["name"], item["line"]))
        return peers[:limit]

    def get_impact_info(
        self,
        symbol: str,
        *,
        depth: int = 3,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        PHASE 9: Analyze blast radius of a symbol (reverse call graph).
        
        Returns symbols that would be affected if this symbol is changed.
        
        Args:
            symbol: Symbol to analyze
            depth: Traversal depth (default 3)
            limit: Maximum results (default 50)
        
        Returns:
            Dict with type="code_impact" and affected symbols list
        """
        affected = self.store.trace_impact(symbol, max_depth=depth, limit=limit)
        
        return {
            "type": "code_impact",
            "symbol": symbol,
            "affected": affected,
            "metrics": {
                "affected_count": len(affected),
                "max_depth": max([item["depth"] for item in affected], default=0),
                "has_cycles": any(item["depth"] >= depth for item in affected),
            },
        }


class BrainAdapter:
    """Adapter for searching Cognitive Memory in Brain Layer 3."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def search(self, query: str, include_private: bool = False, limit: int = 10) -> List[Dict[str, Any]]:
        if not query_layer3:
            return []

        raw_results = query_layer3.search_metadata(query, include_private=include_private, limit=limit)

        results = []
        for result in raw_results:
            metadata = result.get("metadata", {})
            results.append(
                {
                    "type": "doc",
                    "name": metadata.get("source_heading") or metadata.get("source_file"),
                    "kind": metadata.get("source_kind", "markdown"),
                    "path": metadata.get("source_path") or metadata.get("source"),
                    "rank": result.get("score", 0.5),
                    "snippet": result.get("content", "")[:200],
                }
            )
        return results

    def get_unified_context(self, query: str, include_private: bool = False, limit: int = 5) -> List[Dict[str, Any]]:
        return self.search(query, include_private=include_private, limit=limit)
