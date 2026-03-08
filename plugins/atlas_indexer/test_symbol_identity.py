from pathlib import Path

from kit_adapters import AtlasAdapter
from plugins.atlas_indexer.graph_store import GraphStore
from plugins.atlas_indexer.models import CallSite, Symbol


def test_definition_distinguishes_same_name_symbols_across_files(tmp_path: Path):
    """
    Phase 10 spec: file-qualified symbol lookup must resolve the exact symbol.
    """

    parser_a = tmp_path / "parser_a.py"
    parser_b = tmp_path / "parser_b.py"
    store = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    store.update_file(parser_a, [Symbol("parse", "function", str(parser_a), 10)])
    store.update_file(parser_b, [Symbol("parse", "function", str(parser_b), 5)])

    adapter = AtlasAdapter(tmp_path)

    definition = adapter.definition(f"{parser_b.name}::parse")

    assert definition is not None
    assert definition["name"] == "parse"
    assert definition["path"] == str(parser_b)


def test_related_does_not_merge_duplicate_symbol_names(tmp_path: Path):
    """
    Phase 10 spec: graph ranking must not merge same-name symbols across files.
    """

    parser_a = tmp_path / "parser_a.py"
    parser_b = tmp_path / "parser_b.py"
    caller_path = tmp_path / "main.py"
    store = GraphStore(tmp_path / "atlas.db")
    store.update_file(parser_a, [Symbol("parse", "function", str(parser_a), 10)])
    store.update_file(parser_b, [Symbol("parse", "function", str(parser_b), 5)])
    store.update_file(
        caller_path,
        [Symbol("run", "function", str(caller_path), 1)],
        [CallSite("run", "parse", str(caller_path), 2)],
    )

    related = store.search_related_symbols("parse", limit=10)
    parse_rows = sorted(
        (item for item in related if item["name"] == "parse"),
        key=lambda item: str(item["file"]),
    )

    assert [(item["file"], item["degree"]) for item in parse_rows] == [
        (str(parser_a), 1),
        (str(parser_b), 0),
    ]
