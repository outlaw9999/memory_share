from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone as _tz; UTC = _tz.utc

from layer3_metadata import (
    build_chunk_metadata,
    build_tags,
    derive_project_name,
    derive_project_name_from_brain,
    derive_scope,
    extract_primary_heading,
    infer_source_timestamp,
    resolve_workspace_root,
    slugify,
)


WORKSPACE_ROOT = resolve_workspace_root(__file__)
DB_PATH = os.path.join(WORKSPACE_ROOT, "brain", "layer3_index", "neural_memory.db")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Phase 2 metadata into Layer 3.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect changes without writing")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a DB backup")
    return parser.parse_args()


def maybe_backup(db_path: str, enabled: bool) -> str | None:
    if not enabled:
        return None
    backup_path = f"{db_path}.{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.bak"
    shutil.copy2(db_path, backup_path)
    return backup_path


def load_anchor_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    query = (
        "SELECT n.brain_id, b.name AS brain_name, n.id AS neuron_id, n.content, "
        "n.metadata AS neuron_metadata, n.created_at, "
        "f.id AS fiber_id, f.metadata AS fiber_metadata, f.tags AS fiber_tags "
        "FROM neurons n "
        "JOIN brains b ON b.id = n.brain_id "
        "LEFT JOIN fibers f ON f.brain_id = n.brain_id AND f.anchor_neuron_id = n.id "
        "WHERE json_extract(n.metadata, '$.is_anchor') = 1"
    )
    return conn.execute(query).fetchall()


def build_backfilled_metadata(row: sqlite3.Row) -> tuple[dict[str, object], dict[str, object], list[str]]:
    neuron_meta = json.loads(row["neuron_metadata"] or "{}")
    fiber_meta = json.loads(row["fiber_metadata"] or "{}")

    source_path = (
        neuron_meta.get("source")
        or neuron_meta.get("source_path")
        or fiber_meta.get("source")
        or fiber_meta.get("source_path")
    )

    if source_path:
        normalized_source = str(source_path).replace("\\", "/").lower()
        if normalized_source in {"unknown", "unknown/legacy_import.md", "legacy_import.md"}:
            source_path = None
        elif normalized_source.endswith("/unknown") or normalized_source.endswith("/legacy_import.md"):
            source_path = None

    if source_path and not os.path.isabs(str(source_path)):
        source_path = os.path.join(WORKSPACE_ROOT, str(source_path).replace("/", os.sep))

    project_name = (
        neuron_meta.get("project")
        or fiber_meta.get("project")
        or (derive_project_name(str(source_path), WORKSPACE_ROOT) if source_path else None)
        or derive_project_name_from_brain(str(row["brain_name"]))
    )

    if str(project_name).lower() == "prime":
        project_name = "Root"

    timestamp = None
    try:
        if source_path and os.path.exists(str(source_path)):
            timestamp = infer_source_timestamp(str(source_path))
    except Exception:
        timestamp = None

    chunk = {
        "content": row["content"],
        "heading": neuron_meta.get("source_heading"),
        "chunk_index": neuron_meta.get("chunk_index", 0),
        "chunk_count": neuron_meta.get("chunk_count", 1),
    }

    if source_path:
        base_metadata = build_chunk_metadata(
            file_path=str(source_path),
            workspace_root=WORKSPACE_ROOT,
            project_name=str(project_name),
            brain_name=str(row["brain_name"]),
            chunk=chunk,
            source_timestamp=timestamp,
        )
    else:
        content = row["content"]
        heading = extract_primary_heading(content)
        base_metadata = {
            "metadata_version": 2,
            "project": str(project_name),
            "project_slug": slugify(str(project_name)),
            "scope": derive_scope(str(project_name)),
            "privacy": "restricted",
            "brain_name": str(row["brain_name"]),
            "source": "unknown",
            "source_path": "unknown/legacy_import.md",
            "source_file": "legacy_import.md",
            "source_layer": "unknown",
            "source_kind": "legacy_import",
            "chunk_index": int(chunk["chunk_index"]),
            "chunk_count": int(chunk["chunk_count"]),
            "chunk_chars": len(content),
            "content_hash": hashlib.sha1(content.encode("utf-8")).hexdigest()[:16],
            "indexed_at": datetime.now(UTC).isoformat(),
        }
        if heading:
            base_metadata["source_heading"] = heading
            base_metadata["source_heading_slug"] = slugify(heading)[:80]

    # Preserve existing identifiers and timestamps where they already exist.
    merged_neuron = dict(neuron_meta)
    merged_neuron.update(base_metadata)
    merged_neuron["is_anchor"] = True
    if "timestamp" in neuron_meta:
        merged_neuron["timestamp"] = neuron_meta["timestamp"]

    merged_fiber = dict(fiber_meta)
    merged_fiber.update({k: v for k, v in base_metadata.items() if k not in {"chunk_index", "chunk_count", "chunk_chars"}})

    return merged_neuron, merged_fiber, sorted(build_tags(merged_neuron))


def main() -> int:
    args = parse_args()
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"Layer 3 database not found: {DB_PATH}")

    backup_path = maybe_backup(DB_PATH, enabled=not args.no_backup and not args.dry_run)
    if backup_path:
        print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    rows = load_anchor_rows(conn)

    updated_neurons = 0
    updated_fibers = 0

    for row in rows:
        neuron_metadata, fiber_metadata, fiber_tags = build_backfilled_metadata(row)

        updated_neurons += 1
        if row["fiber_id"]:
            updated_fibers += 1

        if args.dry_run:
            continue

        conn.execute(
            "UPDATE neurons SET metadata = ? WHERE brain_id = ? AND id = ?",
            (json.dumps(neuron_metadata, ensure_ascii=False), row["brain_id"], row["neuron_id"]),
        )

        if row["fiber_id"]:
            conn.execute(
                "UPDATE fibers SET metadata = ?, tags = ? WHERE brain_id = ? AND id = ?",
                (
                    json.dumps(fiber_metadata, ensure_ascii=False),
                    json.dumps(fiber_tags, ensure_ascii=False),
                    row["brain_id"],
                    row["fiber_id"],
                ),
            )

    if args.dry_run:
        print(f"Dry run: {updated_neurons} anchor neurons and {updated_fibers} fibers would be updated.")
        return 0

    conn.commit()
    print(f"Updated {updated_neurons} anchor neurons and {updated_fibers} fibers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
