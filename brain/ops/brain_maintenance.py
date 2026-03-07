from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from layer3_metadata import resolve_workspace_root


WORKSPACE_ROOT = resolve_workspace_root(__file__)
DB_PATH = os.path.join(WORKSPACE_ROOT, "brain", "layer3_index", "neural_memory.db")
DIGEST_PATH = os.path.join(WORKSPACE_ROOT, "brain", "layer2_core", "maintenance_digest.md")
STALE_DAYS = 30
WEAK_ACTIVATION = 0.1
WEAK_ACCESS_FREQUENCY = 1
PROMOTION_LIMIT = 8


@dataclass
class AnchorRecord:
    brain_id: str
    brain_name: str
    neuron_id: str
    fiber_id: str | None
    content: str
    neuron_metadata: dict[str, Any]
    fiber_metadata: dict[str, Any]
    fiber_tags: list[str]
    activation_level: float
    access_frequency: int
    created_at: datetime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3 background consolidation for Layer 3.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing them")
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS)
    parser.add_argument("--weak-activation", type=float, default=WEAK_ACTIVATION)
    parser.add_argument("--weak-access", type=int, default=WEAK_ACCESS_FREQUENCY)
    parser.add_argument("--promotion-limit", type=int, default=PROMOTION_LIMIT)
    parser.add_argument(
        "--digest-path",
        default=DIGEST_PATH,
        help="Where to write the human-readable maintenance digest",
    )
    return parser.parse_args()


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def load_anchor_records(conn: sqlite3.Connection) -> list[AnchorRecord]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            n.brain_id,
            b.name AS brain_name,
            n.id AS neuron_id,
            n.content,
            n.metadata AS neuron_metadata,
            n.created_at,
            COALESCE(ns.activation_level, 0.0) AS activation_level,
            COALESCE(ns.access_frequency, 0) AS access_frequency,
            f.id AS fiber_id,
            f.metadata AS fiber_metadata,
            f.tags AS fiber_tags
        FROM neurons n
        JOIN brains b ON b.id = n.brain_id
        LEFT JOIN neuron_states ns
            ON ns.brain_id = n.brain_id AND ns.neuron_id = n.id
        LEFT JOIN fibers f
            ON f.brain_id = n.brain_id AND f.anchor_neuron_id = n.id
        WHERE json_extract(n.metadata, '$.is_anchor') = 1
        """
    ).fetchall()

    records: list[AnchorRecord] = []
    for row in rows:
        records.append(
            AnchorRecord(
                brain_id=row["brain_id"],
                brain_name=row["brain_name"],
                neuron_id=row["neuron_id"],
                fiber_id=row["fiber_id"],
                content=row["content"],
                neuron_metadata=json.loads(row["neuron_metadata"] or "{}"),
                fiber_metadata=json.loads(row["fiber_metadata"] or "{}"),
                fiber_tags=json.loads(row["fiber_tags"] or "[]"),
                activation_level=float(row["activation_level"] or 0.0),
                access_frequency=int(row["access_frequency"] or 0),
                created_at=parse_datetime(row["created_at"]),
            )
        )
    return records


def content_key(record: AnchorRecord) -> str:
    return str(record.neuron_metadata.get("content_hash") or record.content.strip())


def freshness_bonus(created_at: datetime, now: datetime) -> float:
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return max(0.0, 30.0 - age_days) * 0.01


def maintenance_bucket(age_days: float) -> str:
    if age_days <= 7:
        return "hot"
    if age_days <= 45:
        return "warm"
    return "cold"


def anchor_score(record: AnchorRecord, now: datetime) -> float:
    score = float(record.access_frequency) * 0.1
    score += float(record.activation_level) * 0.5
    score += freshness_bonus(record.created_at, now)
    if record.neuron_metadata.get("source_heading"):
        score += 0.1
    if record.neuron_metadata.get("source_kind") in {"daily_log", "project_stream", "core_memory"}:
        score += 0.05
    return round(score, 4)


def pick_canonical(group: list[AnchorRecord], now: datetime) -> AnchorRecord:
    return max(
        group,
        key=lambda record: (
            anchor_score(record, now),
            record.access_frequency,
            record.activation_level,
            -record.created_at.timestamp(),
        ),
    )


def determine_status(
    records: list[AnchorRecord],
    *,
    now: datetime,
    stale_days: int,
    weak_activation: float,
    weak_access: int,
    promotion_limit: int,
) -> tuple[dict[str, dict[str, Any]], list[AnchorRecord]]:
    by_content: dict[tuple[str, str], list[AnchorRecord]] = defaultdict(list)
    for record in records:
        by_content[(record.brain_id, content_key(record))].append(record)

    result: dict[str, dict[str, Any]] = {}
    promotion_candidates: list[AnchorRecord] = []

    for group in by_content.values():
        canonical = pick_canonical(group, now)
        for record in group:
            age_days = max(0.0, (now - record.created_at).total_seconds() / 86400.0)
            duplicate = len(group) > 1 and record.neuron_id != canonical.neuron_id
            stale_candidate = (
                age_days >= stale_days
                and record.activation_level <= weak_activation
                and record.access_frequency <= weak_access
            )
            score = anchor_score(record, now)
            promotable = (
                not duplicate
                and not stale_candidate
                and record.neuron_metadata.get("privacy") != "private"
                and record.neuron_metadata.get("source_kind") != "legacy_import"
            )

            result[record.neuron_id] = {
                "score": score,
                "age_days": round(age_days, 2),
                "duplicate_status": "duplicate" if duplicate else ("canonical" if len(group) > 1 else "unique"),
                "duplicate_of": canonical.neuron_id if duplicate else None,
                "duplicate_group_size": len(group),
                "stale_candidate": stale_candidate,
                "promotion_candidate": promotable,
                "maintenance_bucket": maintenance_bucket(age_days),
            }

            if promotable:
                promotion_candidates.append(record)

    promotion_candidates.sort(key=lambda record: result[record.neuron_id]["score"], reverse=True)
    return result, promotion_candidates[:promotion_limit]


def merge_maintenance_metadata(metadata: dict[str, Any], status: dict[str, Any], now: datetime) -> dict[str, Any]:
    merged = dict(metadata)
    merged["maintenance"] = {
        "version": 1,
        "last_maintained_at": now.isoformat(),
        **status,
    }
    return merged


def merge_fiber_tags(tags: list[str], status: dict[str, Any]) -> list[str]:
    tag_set = set(tags)
    tag_set.add(f"maintenance:{status['maintenance_bucket']}")
    if status["duplicate_status"] == "duplicate":
        tag_set.add("maintenance:duplicate")
    if status["stale_candidate"]:
        tag_set.add("maintenance:stale_candidate")
    if status["promotion_candidate"]:
        tag_set.add("maintenance:promotion_candidate")
    return sorted(tag_set)


def write_updates(
    conn: sqlite3.Connection,
    records: list[AnchorRecord],
    status_map: dict[str, dict[str, Any]],
    now: datetime,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    updated_neurons = 0
    updated_fibers = 0

    for record in records:
        status = status_map[record.neuron_id]
        neuron_metadata = merge_maintenance_metadata(record.neuron_metadata, status, now)
        fiber_metadata = merge_maintenance_metadata(record.fiber_metadata, status, now)
        fiber_tags = merge_fiber_tags(record.fiber_tags, status)

        updated_neurons += 1
        if record.fiber_id:
            updated_fibers += 1

        if dry_run:
            continue

        conn.execute(
            "UPDATE neurons SET metadata = ? WHERE brain_id = ? AND id = ?",
            (json.dumps(neuron_metadata, ensure_ascii=False), record.brain_id, record.neuron_id),
        )

        if record.fiber_id:
            conn.execute(
                "UPDATE fibers SET metadata = ?, tags = ? WHERE brain_id = ? AND id = ?",
                (
                    json.dumps(fiber_metadata, ensure_ascii=False),
                    json.dumps(fiber_tags, ensure_ascii=False),
                    record.brain_id,
                    record.fiber_id,
                ),
            )

    if not dry_run:
        conn.commit()

    return updated_neurons, updated_fibers


def render_digest(
    *,
    now: datetime,
    records: list[AnchorRecord],
    status_map: dict[str, dict[str, Any]],
    promotion_candidates: list[AnchorRecord],
    stale_days: int,
    weak_activation: float,
    weak_access: int,
) -> str:
    duplicate_count = sum(1 for status in status_map.values() if status["duplicate_status"] == "duplicate")
    stale_count = sum(1 for status in status_map.values() if status["stale_candidate"])
    promotion_count = sum(1 for status in status_map.values() if status["promotion_candidate"])

    lines = [
        "---",
        "title: Maintenance Digest",
        "scope: workspace",
        "privacy: shareable",
        "owner: antigravity",
        f"updated_at: {now.date().isoformat()}",
        "status: active",
        "---",
        "",
        "# Maintenance Digest",
        "",
        f"- Last run: {now.isoformat()}",
        f"- Anchors scanned: {len(records)}",
        f"- Promotion candidates: {promotion_count}",
        f"- Duplicate candidates: {duplicate_count}",
        f"- Stale candidates: {stale_count}",
        f"- Thresholds: stale_days={stale_days}, weak_activation={weak_activation}, weak_access={weak_access}",
        "",
        "## Promotion Candidates",
        "",
    ]

    if promotion_candidates:
        for record in promotion_candidates:
            status = status_map[record.neuron_id]
            metadata = record.neuron_metadata
            heading = metadata.get("source_heading") or "(no heading)"
            source = metadata.get("source_path") or metadata.get("source") or "(unknown source)"
            snippet = record.content.replace("\ufeff", "").replace("\n", " ")[:180]
            lines.extend(
                [
                    f"### {metadata.get('project', 'unknown')} :: score {status['score']}",
                    f"- Heading: {heading}",
                    f"- Source: {source}",
                    f"- Bucket: {status['maintenance_bucket']}",
                    f"- Snippet: {snippet}",
                    "",
                ]
            )
    else:
        lines.extend(["No promotion candidates found.", ""])

    lines.extend(["## Duplicate Candidates", ""])
    duplicate_records = [record for record in records if status_map[record.neuron_id]["duplicate_status"] == "duplicate"]
    if duplicate_records:
        for record in duplicate_records:
            status = status_map[record.neuron_id]
            metadata = record.neuron_metadata
            lines.extend(
                [
                    f"- {record.neuron_id} -> duplicate_of={status['duplicate_of']} "
                    f"project={metadata.get('project', 'unknown')} source={metadata.get('source_path', metadata.get('source', 'unknown'))}",
                ]
            )
        lines.append("")
    else:
        lines.extend(["No duplicate candidates found.", ""])

    lines.extend(["## Stale Candidates", ""])
    stale_records = [record for record in records if status_map[record.neuron_id]["stale_candidate"]]
    if stale_records:
        for record in stale_records:
            status = status_map[record.neuron_id]
            metadata = record.neuron_metadata
            heading = metadata.get("source_heading") or "(no heading)"
            lines.extend(
                [
                    f"- project={metadata.get('project', 'unknown')} age_days={status['age_days']} heading={heading}",
                ]
            )
        lines.append("")
    else:
        lines.extend(["No stale candidates found.", ""])

    lines.extend(
        [
            "## Notes",
            "",
            "- Promotion candidates are safe deterministic rollups, not LLM-written summaries.",
            "- Duplicate and stale states are metadata flags only; no destructive cleanup is performed in this phase.",
            "- Use this digest as a review surface before later graph or transaction work.",
            "",
        ]
    )
    return "\n".join(lines)


def write_digest(path: str, content: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def main() -> int:
    args = parse_args()
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"Layer 3 database not found: {DB_PATH}")

    now = datetime.now(UTC)
    conn = sqlite3.connect(DB_PATH)
    records = load_anchor_records(conn)

    status_map, promotion_candidates = determine_status(
        records,
        now=now,
        stale_days=args.stale_days,
        weak_activation=args.weak_activation,
        weak_access=args.weak_access,
        promotion_limit=args.promotion_limit,
    )

    updated_neurons, updated_fibers = write_updates(
        conn,
        records,
        status_map,
        now,
        dry_run=args.dry_run,
    )

    digest = render_digest(
        now=now,
        records=records,
        status_map=status_map,
        promotion_candidates=promotion_candidates,
        stale_days=args.stale_days,
        weak_activation=args.weak_activation,
        weak_access=args.weak_access,
    )
    write_digest(args.digest_path, digest, dry_run=args.dry_run)

    print(f"Anchors scanned: {len(records)}")
    print(f"Neurons updated: {updated_neurons}")
    print(f"Fibers updated: {updated_fibers}")
    print(f"Promotion candidates: {sum(1 for status in status_map.values() if status['promotion_candidate'])}")
    print(f"Duplicate candidates: {sum(1 for status in status_map.values() if status['duplicate_status'] == 'duplicate')}")
    print(f"Stale candidates: {sum(1 for status in status_map.values() if status['stale_candidate'])}")
    if args.dry_run:
        print("Dry run only. No DB or digest changes written.")
    else:
        print(f"Digest written to: {args.digest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
