import json
from pathlib import Path

from kit_adapters import AtlasAdapter
from plugins.atlas_indexer.graph_store import GraphStore
from plugins.atlas_indexer.indexer import AtlasIndexer
from plugins.atlas_indexer.models import Symbol


class FakeEvent:
    def __init__(self, txn):
        self.txn = txn


def test_atlas_adapter_symbol_callers_and_snippet(tmp_path: Path):
    source_path = tmp_path / "service.py"
    source_path.write_text(
        "def helper():\n"
        "    return 1\n\n"
        "def run():\n"
        "    helper()\n"
        "    return helper()\n",
        encoding="utf-8",
    )

    graph = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    indexer.handle_event(FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "service.py"}))
    assert indexer.poll() == ["service.py"]

    adapter = AtlasAdapter(tmp_path)

    symbol_results = adapter.search("run", limit=5)
    assert symbol_results[0]["type"] == "code_symbol"
    assert symbol_results[0]["name"] == "run"

    caller_results = adapter.callers("helper", limit=5)
    assert caller_results == [
        {
            "type": "code_caller",
            "caller": "run",
            "callee": "helper",
            "path": str(source_path),
            "line": 5,
            "rank": 1.0,
        },
        {
            "type": "code_caller",
            "caller": "run",
            "callee": "helper",
            "path": str(source_path),
            "line": 6,
            "rank": 1.0,
        },
    ]

    snippet = adapter.snippet("service.py:4", radius=1)
    assert snippet["start_line"] == 3
    assert snippet["end_line"] == 5
    assert "def run()" in snippet["snippet"]

    context = adapter.get_unified_context("run", caller_limit=5, callee_limit=5, snippet_radius=1)
    assert context["type"] == "code_context"
    assert context["definition"]["name"] == "run"
    assert context["callers"] == []
    assert [item["callee"] for item in context["callees"]] == ["helper", "helper"]
    assert "def run()" in context["snippet"]["snippet"]
    assert context["metrics"] == {
        "caller_count": 0,
        "callee_count": 2,
        "has_definition": True,
    }


def test_atlas_adapter_context_prefers_production_definition(tmp_path: Path):
    prod_path = tmp_path / "pkg" / "service.py"
    test_path = tmp_path / "tests" / "test_service.py"
    prod_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)
    prod_path.write_text("def run():\n    return 1\n", encoding="utf-8")
    test_path.write_text("def run():\n    return 2\n", encoding="utf-8")

    store = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    store.update_file(prod_path, [Symbol("run", "function", str(prod_path), 1)])
    store.update_file(test_path, [Symbol("run", "function", str(test_path), 1)])

    adapter = AtlasAdapter(tmp_path)
    context = adapter.get_unified_context("run", snippet_radius=1)

    assert context["definition"]["path"] == str(prod_path)
    assert "return 1" in context["snippet"]["snippet"]


def test_atlas_adapter_related_returns_neighbors_and_peers(tmp_path: Path):
    source_path = tmp_path / "memory_store.py"
    source_path.write_text(
        "def write_memory():\n"
        "    flush_memory()\n"
        "    return read_memory()\n\n"
        "def read_memory():\n"
        "    return 1\n\n"
        "def flush_memory():\n"
        "    return 0\n\n"
        "def sync_memory():\n"
        "    return write_memory()\n",
        encoding="utf-8",
    )

    graph = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    indexer.handle_event(FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "memory_store.py"}))
    assert indexer.poll() == ["memory_store.py"]

    adapter = AtlasAdapter(tmp_path)
    related = adapter.get_related_info("write_memory", similar_limit=5, caller_limit=5, callee_limit=5, module_limit=8)

    assert related["type"] == "code_related"
    assert related["definition"]["name"] == "write_memory"
    assert [item["caller"] for item in related["related"]["callers"]] == ["sync_memory"]
    assert [item["callee"] for item in related["related"]["callees"]] == ["flush_memory", "read_memory"]
    assert "write_memory" not in [item["name"] for item in related["related"]["similar"]]
    assert [item["name"] for item in related["related"]["module_peers"]] == [
        "flush_memory",
        "read_memory",
        "sync_memory",
    ]
    assert related["metrics"] == {
        "similar_count": 3,
        "caller_count": 1,
        "callee_count": 2,
        "module_peer_count": 3,
        "has_definition": True,
    }


def test_kit_json_contract_for_symbol_callers_and_snippet(tmp_path: Path, monkeypatch, capsys):
    source_path = tmp_path / "worker.py"
    source_path.write_text(
        "def task():\n"
        "    return 1\n\n"
        "def main():\n"
        "    return task()\n",
        encoding="utf-8",
    )

    graph = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    indexer.handle_event(FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "worker.py"}))
    assert indexer.poll() == ["worker.py"]

    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_ROOT", str(tmp_path))

    import kit

    monkeypatch.setattr("sys.argv", ["kit.py", "symbol", "task", "--json"])
    kit.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "task"
    assert payload["results"][0]["type"] == "code_symbol"

    monkeypatch.setattr("sys.argv", ["kit.py", "callers", "task", "--json"])
    kit.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "task"
    assert payload["results"][0]["caller"] == "main"

    monkeypatch.setattr("sys.argv", ["kit.py", "snippet", "worker.py:4", "--radius", "1", "--json"])
    kit.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "worker.py:4"
    assert payload["results"][0]["type"] == "code_snippet"

    monkeypatch.setattr(
        "sys.argv",
        ["kit.py", "context", "task", "--radius", "1", "--callers-limit", "5", "--callees-limit", "5", "--json"],
    )
    kit.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "task"
    context = payload["results"][0]
    assert context["type"] == "code_context"
    assert context["definition"]["name"] == "task"
    assert context["callers"][0]["caller"] == "main"
    assert context["callees"] == []
    assert context["snippet"]["type"] == "code_snippet"
    assert isinstance(context["docs"], list)
    assert context["metrics"] == {
        "caller_count": 1,
        "callee_count": 0,
        "doc_count": 0,
        "has_definition": True,
    }

    monkeypatch.setattr(
        "sys.argv",
        ["kit.py", "related", "task", "--similar-limit", "5", "--callers-limit", "5", "--callees-limit", "5", "--json"],
    )
    kit.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "task"
    related = payload["results"][0]
    assert related["type"] == "code_related"
    assert related["definition"]["name"] == "task"
    assert related["related"]["callers"][0]["caller"] == "main"
    assert related["related"]["callees"] == []
    assert all(item["name"] != "task" for item in related["related"]["similar"])
    assert related["metrics"] == {
        "similar_count": 0,
        "caller_count": 1,
        "callee_count": 0,
        "module_peer_count": 1,
        "has_definition": True,
    }


def test_phase_8_contract_is_stable(tmp_path: Path, monkeypatch, capsys):
    """
    REGRESSION TEST: Phase 8 (Context Engine) JSON contract is FROZEN.
    
    This test ensures that the JSON structure returned by Phase 8 commands
    (symbol, context, callers, snippet) never drifts, even after Phase 9/10 changes.
    
    Agent tool schemas depend on these exact field names and types.
    
    Related: ARCHITECTURE.md Phase 8
    """
    source_path = tmp_path / "module.py"
    source_path.write_text(
        "def api():\n"
        "    return 1\n\n"
        "def caller():\n"
        "    return api()\n",
        encoding="utf-8",
    )

    graph = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    indexer.handle_event(FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "module.py"}))
    assert indexer.poll() == ["module.py"]

    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_ROOT", str(tmp_path))

    import kit

    # Phase 8: kit symbol contract
    monkeypatch.setattr("sys.argv", ["kit.py", "symbol", "api", "--json"])
    kit.main()
    payload = json.loads(capsys.readouterr().out)
    
    # Frozen fields at top level
    assert {"query", "results"}.issubset(set(payload.keys()))
    result = payload["results"][0]
    assert {"type", "name", "kind", "path", "line", "rank"}.issubset(set(result.keys()))
    assert result["type"] == "code_symbol"

    # Phase 8: kit context contract
    monkeypatch.setattr(
        "sys.argv",
        ["kit.py", "context", "api", "--json"],
    )
    kit.main()
    payload = json.loads(capsys.readouterr().out)
    context = payload["results"][0]
    
    # Frozen top-level structure
    assert {"type", "symbol", "definition", "callers", "callees", "snippet", "metrics", "docs"}.issubset(
        set(context.keys())
    )
    assert context["type"] == "code_context"
    
    # Frozen metrics structure
    assert {"caller_count", "callee_count", "doc_count", "has_definition"}.issubset(set(context["metrics"].keys()))
    
    # Frozen definition structure
    assert {"type", "name", "kind", "path", "line", "rank"} == set(context["definition"].keys())
    
    # Frozen callers array element structure
    for caller_item in context["callers"]:
        assert {"type", "caller", "callee", "path", "line", "rank"}.issubset(set(caller_item.keys()))


def test_phase_9_impact_traversal_basic(tmp_path: Path):
    """
    PHASE 9: Basic reverse call graph traversal.
    
    Graph:
        caller_a → target
        caller_b → caller_a
    
    impact(target) = [caller_a, caller_b]  (recursive, up to depth limit)
    impact(caller_a) = [caller_b]
    """
    source_path = tmp_path / "service.py"
    source_path.write_text(
        "def target():\n"
        "    return 1\n\n"
        "def caller_a():\n"
        "    return target()\n\n"
        "def caller_b():\n"
        "    return caller_a()\n",
        encoding="utf-8",
    )

    store = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=store)
    indexer.coalesce_window_seconds = 0.0
    indexer.handle_event(FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "service.py"}))
    assert indexer.poll() == ["service.py"]

    adapter = AtlasAdapter(tmp_path)
    
    # Test impact of target() - finds all callers recursively
    impact_target = adapter.get_impact_info("target", depth=3, limit=50)
    assert impact_target["type"] == "code_impact"
    assert impact_target["symbol"] == "target"
    assert len(impact_target["affected"]) == 2
    assert impact_target["affected"][0]["name"] == "caller_a"
    assert impact_target["affected"][0]["depth"] == 1
    assert impact_target["affected"][1]["name"] == "caller_b"
    assert impact_target["affected"][1]["depth"] == 2
    
    # Test impact of caller_a()
    impact_caller_a = adapter.get_impact_info("caller_a", depth=3, limit=50)
    assert len(impact_caller_a["affected"]) == 1
    assert impact_caller_a["affected"][0]["name"] == "caller_b"
    assert impact_caller_a["affected"][0]["depth"] == 1


def test_phase_9_impact_respects_depth_limit(tmp_path: Path):
    """
    PHASE 9: Depth limit prevents traversal beyond max_depth.
    
    Graph:
        d → c → b → a
    
    impact(a, depth=2) should return [b, c] but NOT [d]
    """
    source_path = tmp_path / "chain.py"
    source_path.write_text(
        "def a():\n"
        "    return 1\n\n"
        "def b():\n"
        "    return a()\n\n"
        "def c():\n"
        "    return b()\n\n"
        "def d():\n"
        "    return c()\n",
        encoding="utf-8",
    )

    store = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=store)
    indexer.coalesce_window_seconds = 0.0
    indexer.handle_event(FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "chain.py"}))
    assert indexer.poll() == ["chain.py"]

    adapter = AtlasAdapter(tmp_path)
    
    # With depth=2, should find b and c but not d
    impact = adapter.get_impact_info("a", depth=2, limit=50)
    affected_names = {item["name"] for item in impact["affected"]}
    
    assert "b" in affected_names  # depth 1
    assert "c" in affected_names  # depth 2
    assert "d" not in affected_names  # depth 3 (beyond limit)


def test_phase_9_impact_handles_cycles(tmp_path: Path):
    """
    PHASE 9: Depth limit prevents infinite loops from cycles.
    
    Graph:
        a → b → a (cycle)
    
    impact(a, depth=3) should complete without hang and mark has_cycles=True
    """
    source_path = tmp_path / "cycle.py"
    source_path.write_text(
        "def a():\n"
        "    return b()\n\n"
        "def b():\n"
        "    return a()\n",
        encoding="utf-8",
    )

    store = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=store)
    indexer.coalesce_window_seconds = 0.0
    indexer.handle_event(FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "cycle.py"}))
    assert indexer.poll() == ["cycle.py"]

    adapter = AtlasAdapter(tmp_path)
    
    # Should not hang, should respect depth limit
    impact = adapter.get_impact_info("a", depth=2, limit=50)
    
    # Should find b (depth 1)
    assert any(item["name"] == "b" for item in impact["affected"])
    
    # No infinite loop, completes normally
    assert impact["type"] == "code_impact"


def test_phase_9_impact_json_contract(tmp_path: Path, monkeypatch, capsys):
    """
    PHASE 9: JSON contract for kit impact command.
    
    Output structure must be:
    {
        "type": "code_impact",
        "symbol": "<symbol>",
        "affected": [{"name": "...", "depth": ..., "path": "...", "line": ...}],
        "metrics": {"affected_count": ..., "max_depth": ..., "has_cycles": ...}
    }
    """
    source_path = tmp_path / "api.py"
    source_path.write_text(
        "def api():\n"
        "    return 1\n\n"
        "def handler():\n"
        "    return api()\n",
        encoding="utf-8",
    )

    store = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=store)
    indexer.coalesce_window_seconds = 0.0
    indexer.handle_event(FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "api.py"}))
    assert indexer.poll() == ["api.py"]

    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_ROOT", str(tmp_path))

    import kit

    # Test impact command output
    monkeypatch.setattr("sys.argv", ["kit.py", "impact", "api", "--json"])
    kit.main()
    payload = json.loads(capsys.readouterr().out)
    
    # Frozen top-level structure
    assert {"query", "results"}.issubset(set(payload.keys()))
    impact = payload["results"][0]
    assert {"type", "symbol", "affected", "metrics"}.issubset(set(impact.keys()))
    assert impact["type"] == "code_impact"
    
    # Frozen affected array element structure
    for item in impact["affected"]:
        assert {"name", "depth", "path", "line"}.issubset(set(item.keys()))
    
    # Frozen metrics structure
    assert {"affected_count", "max_depth", "has_cycles"}.issubset(set(impact["metrics"].keys()))
