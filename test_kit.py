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
