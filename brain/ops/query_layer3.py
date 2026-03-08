from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

from layer3_metadata import resolve_workspace_root, slugify


WORKSPACE_ROOT = resolve_workspace_root(__file__)
DB_PATH = os.path.join(WORKSPACE_ROOT, "brain", "layer3_index", "neural_memory.db")


def build_fts_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9_]+", query.lower())
    if not terms:
        raise ValueError("Query does not contain searchable terms.")
    return " AND ".join(terms)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Layer 3 with metadata filters.")
    parser.add_argument("query", help="Free-text query for anchor memories")
    parser.add_argument("--brain", help="Filter by brain name")
    parser.add_argument("--project", help="Filter by project name or slug")
    parser.add_argument("--scope", choices=["workspace", "project"])
    parser.add_argument("--privacy", choices=["shareable", "restricted", "private"])
    parser.add_argument("--include-private", action="store_true")
    parser.add_argument("--source-kind", help="Filter by source kind")
    parser.add_argument("--source-layer", help="Filter by source layer")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    return parser.parse_args()


def build_sql(args: argparse.Namespace) -> tuple[str, list[object]]:
    query = (
        "SELECT b.name AS brain_name, n.id, n.content, n.metadata, n.created_at, "
        "COALESCE(ns.access_frequency, 0) AS access_frequency, "
        "COALESCE(ns.activation_level, 0.0) AS activation_level, "
        "-fts.rank AS text_score "
        "FROM neurons n "
        "JOIN brains b ON b.id = n.brain_id "
        "JOIN neurons_fts fts ON n.rowid = fts.rowid "
        "LEFT JOIN neuron_states ns ON ns.brain_id = n.brain_id AND ns.neuron_id = n.id "
        "WHERE fts.neurons_fts MATCH ? "
        "AND json_extract(n.metadata, '$.is_anchor') = 1"
    )
    params: list[object] = [build_fts_query(args.query)]

    if args.brain:
        query += " AND b.name = ?"
        params.append(args.brain)

    if args.project:
        project_slug = slugify(args.project)
        query += (
            " AND (json_extract(n.metadata, '$.project') = ? "
            "OR json_extract(n.metadata, '$.project_slug') = ?)"
        )
        params.extend([args.project, project_slug])

    if args.scope:
        query += " AND json_extract(n.metadata, '$.scope') = ?"
        params.append(args.scope)

    if args.privacy:
        query += " AND json_extract(n.metadata, '$.privacy') = ?"
        params.append(args.privacy)
    elif not args.include_private:
        query += " AND COALESCE(json_extract(n.metadata, '$.privacy'), 'shareable') != 'private'"

    if args.source_kind:
        query += " AND json_extract(n.metadata, '$.source_kind') = ?"
        params.append(args.source_kind)

    if args.source_layer:
        query += " AND json_extract(n.metadata, '$.source_layer') = ?"
        params.append(args.source_layer)

    query += " ORDER BY text_score DESC LIMIT ?"
    params.append(max(1, args.limit * 5))
    return query, params


def search_metadata(
    query: str,
    brain: str | None = None,
    project: str | None = None,
    scope: str | None = None,
    privacy: str | None = None,
    include_private: bool = False,
    source_kind: str | None = None,
    source_layer: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Programmatic entry point for searching Layer 3 metadata."""
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Prepare mock args for build_sql
    class Args:
        pass

    args = Args()
    args.query = query
    args.brain = brain
    args.project = project
    args.scope = scope
    args.privacy = privacy
    args.include_private = include_private
    args.source_kind = source_kind
    args.source_layer = source_layer
    args.limit = limit

    sql, params = build_sql(args) # type: ignore
    rows = conn.execute(sql, params).fetchall()
    results = [rank_row(row) for row in rows]
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[: max(1, limit)]


def rank_row(row: sqlite3.Row) -> dict[str, Any]:
    metadata = json.loads(row["metadata"] or "{}")
    created_at = metadata.get("indexed_at") or metadata.get("source_timestamp") or row["created_at"]

    freshness_bonus = 0.0
    try:
        dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
        freshness_bonus = max(0.0, 30.0 - age_days) * 0.01
    except Exception:
        pass

    score = float(row["text_score"]) + float(row["access_frequency"]) * 0.1
    score += float(row["activation_level"]) * 0.5
    score += freshness_bonus

    return {
        "brain_name": row["brain_name"],
        "neuron_id": row["id"],
        "score": round(score, 4),
        "content": row["content"],
        "metadata": metadata,
        "access_frequency": row["access_frequency"],
        "activation_level": row["activation_level"],
    }


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"Layer 3 database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    sql, params = build_sql(args)
    rows = conn.execute(sql, params).fetchall()
    results = [rank_row(row) for row in rows]
    results.sort(key=lambda item: item["score"], reverse=True)
    results = results[: max(1, args.limit)]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    if not results:
        print("No Layer 3 matches found.")
        return 0

    for index, item in enumerate(results, 1):
        metadata = item["metadata"]
        heading = metadata.get("source_heading") or "(no heading)"
        source = metadata.get("source_path") or metadata.get("source") or "(unknown source)"
        snippet = str(item["content"]).replace("\ufeff", "").replace("\n", " ")
        print(f"[{index}] score={item['score']} brain={item['brain_name']}")
        print(
            "    "
            f"project={metadata.get('project', 'unknown')} "
            f"scope={metadata.get('scope', 'unknown')} "
            f"privacy={metadata.get('privacy', 'unknown')}"
        )
        print(f"    heading={heading}")
        print(f"    source={source}")
        print(f"    content={snippet[:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
