#!/usr/bin/env python3
import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from plugins.atlas_indexer.graph_store import GraphStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Atlas symbol and caller queries.")
    parser.add_argument("--symbols", type=int, default=100_000, help="Total symbol rows to generate.")
    parser.add_argument("--calls", type=int, default=200_000, help="Total call rows to generate.")
    parser.add_argument("--iterations", type=int, default=200, help="Timed query iterations.")
    parser.add_argument("--db-path", type=Path, help="Optional SQLite path. Defaults to a temporary file.")
    return parser.parse_args()


def build_store(db_path: Path, symbol_count: int, call_count: int) -> GraphStore:
    store = GraphStore(db_path)
    symbol_rows = []
    target_symbols = max(100, symbol_count // 200)
    for i in range(symbol_count):
        if i < target_symbols:
            name = f"kernel_write_{i:05d}"
        else:
            name = f"symbol_{i:07d}"
        symbol_rows.append((name, "function", f"src/file_{i % 2000:04d}.py", (i % 400) + 1))

    call_rows = []
    target_calls = max(500, call_count // 100)
    for i in range(call_count):
        callee = "helper" if i < target_calls else f"callee_{i % 5000:04d}"
        caller = f"caller_{i:07d}"
        file_name = f"src/module_{i % 3000:04d}.py"
        call_rows.append((caller, callee, file_name, (i % 500) + 1))

    with store.conn:
        store.conn.executemany(
            "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
            symbol_rows,
        )
        store.conn.executemany(
            "INSERT INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
            call_rows,
        )

    return store


def measure_ms(fn, iterations: int) -> dict[str, float]:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        fn()
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        samples.append(elapsed_ms)

    ordered = sorted(samples)
    p95_index = min(len(ordered) - 1, round(len(ordered) * 0.95) - 1)
    return {
        "mean_ms": round(statistics.fmean(samples), 3),
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": round(ordered[p95_index], 3),
    }


def explain_callers(store: GraphStore) -> list[str]:
    rows = store.conn.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT caller, callee, file, line
        FROM calls
        WHERE callee = ?
        ORDER BY file, line
        LIMIT ?
        """,
        ("helper", 50),
    ).fetchall()
    return [detail for *_, detail in rows]


def detect_fts_bloat(store: GraphStore, query: str, iterations: int) -> dict[str, float | str | None]:
    before = measure_ms(
        lambda: store.search_symbols(query, limit=20, fuzzy=False),
        iterations,
    )
    try:
        store.conn.execute("INSERT INTO symbol_fts(symbol_fts) VALUES ('optimize')")
    except Exception:
        return {"status": "unsupported"}

    after = measure_ms(
        lambda: store.search_symbols(query, limit=20, fuzzy=False),
        iterations,
    )
    ratio = round(before["mean_ms"] / after["mean_ms"], 3) if after["mean_ms"] else None
    return {
        "status": "ok",
        "before_mean_ms": before["mean_ms"],
        "after_mean_ms": after["mean_ms"],
        "ratio": ratio,
    }


def main() -> None:
    args = parse_args()
    if args.db_path is not None:
        db_path = args.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        cleanup_dir = None
    else:
        cleanup_dir = tempfile.TemporaryDirectory()
        db_path = Path(cleanup_dir.name) / "atlas-bench.db"

    store = build_store(db_path, args.symbols, args.calls)
    try:
        payload = {
            "db_path": str(db_path),
            "symbols": args.symbols,
            "calls": args.calls,
            "iterations": args.iterations,
            "symbol_prefix_query": {
                "query": "kernel_wr",
                "metrics": measure_ms(
                    lambda: store.search_symbols("kernel_wr", limit=20, fuzzy=False),
                    args.iterations,
                ),
            },
            "symbol_fuzzy_query": {
                "query": "nel_wri",
                "metrics": measure_ms(
                    lambda: store.search_symbols("nel_wri", limit=20, fuzzy=True),
                    args.iterations,
                ),
            },
            "callers_query": {
                "query": "helper",
                "metrics": measure_ms(
                    lambda: store.find_callers("helper", limit=50),
                    args.iterations,
                ),
                "plan": explain_callers(store),
            },
            "fts_bloat_check": detect_fts_bloat(
                store,
                query="kernel_wr",
                iterations=max(20, args.iterations // 4),
            ),
        }
        print(json.dumps(payload, indent=2))
    finally:
        store.conn.close()
        if cleanup_dir is not None:
            cleanup_dir.cleanup()


if __name__ == "__main__":
    main()
