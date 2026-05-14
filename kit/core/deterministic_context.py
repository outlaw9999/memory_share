# kit/core/deterministic_context.py
# v1.2.5: Context Compiler + Deterministic Hashing
#
# Core logic:
#   SQLite → deterministic JSON → blake2b hash → execution_context.json

import hashlib
import json
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_VERSION = "1.2.5"
SCHEMA_VERSION = "1.0"


def deterministic_json(obj: dict[str, Any]) -> str:
    """
    Serialize dict to deterministic JSON.

    Guarantees:
    - Same input → same output every time
    - No random key ordering
    - ASCII-safe for protocol transfer
    """
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def context_hash(context: dict[str, Any]) -> str:
    """Generate blake2b hash of context content."""
    json_str = deterministic_json(context)
    return hashlib.blake2b(json_str.encode("utf-8"), digest_size=32).hexdigest()


def now_iso() -> str:
    """Current timestamp in ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def query_sorted_invariants(conn) -> list[dict[str, Any]]:
    """Query invariants with deterministic sorting."""
    sql = """
        SELECT n.uid, o.content, o.importance, o.created_at, o.layer, o.tag
        FROM observations o
        JOIN nodes n ON o.node_id = n.id
        WHERE o.tag = 'invariant' AND o.is_active = 1
        ORDER BY o.importance DESC, o.created_at ASC, n.uid ASC
        LIMIT 10
    """
    rows = conn.execute(sql).fetchall()
    return [
        {
            "uid": r["uid"],
            "content": r["content"],
            "importance": r["importance"],
            "created_at": r["created_at"],
            "layer": r["layer"],
        }
        for r in rows
    ]


def query_sorted_decisions(conn) -> list[dict[str, Any]]:
    """Query decisions with deterministic sorting."""
    sql = """
        SELECT n.uid, o.content, o.importance, o.created_at, o.layer, o.tag
        FROM observations o
        JOIN nodes n ON o.node_id = n.id
        WHERE o.tag = 'decision' AND o.is_active = 1
        ORDER BY o.importance DESC, o.created_at ASC, n.uid ASC
        LIMIT 10
    """
    rows = conn.execute(sql).fetchall()
    return [
        {
            "uid": r["uid"],
            "content": r["content"],
            "importance": r["importance"],
            "created_at": r["created_at"],
            "layer": r["layer"],
        }
        for r in rows
    ]


def load_skill_index(kit_dir: Path) -> list[dict[str, Any]]:
    """Load skill registry from .kit/skills/ directory."""
    skills_dir = kit_dir / "skills"
    if not skills_dir.exists():
        return []

    skills = []
    for yaml_file in sorted(skills_dir.glob("*.yaml")):
        try:
            import yaml

            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            skills.append(
                {
                    "name": yaml_file.stem,
                    "triggers": data.get("triggers", []),
                    "deterministic": data.get("deterministic", False),
                    "safety_level": data.get("safety_level", "unknown"),
                    "side_effect": data.get("side_effect", "none"),
                }
            )
        except Exception:
            continue
    return skills


def load_friction_log(kit_dir: Path) -> dict[str, list]:
    """Load friction log from .kit/friction.json."""
    friction_file = kit_dir / "friction.json"
    if not friction_file.exists():
        return {"active": [], "resolved": []}
    try:
        data = json.loads(friction_file.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {"active": [], "resolved": []}


def assemble_execution_context(brain) -> dict[str, Any]:
    """
    Assemble execution_context.json from SQLite.

    Steps:
    1. Query invariants (sorted deterministic)
    2. Query decisions (sorted deterministic)
    3. Load skill index
    4. Load friction log
    5. Build context dict
    6. Generate hash
    7. Return complete context
    """
    kit_dir = brain.root_path / ".kit"
    kit_dir.mkdir(parents=True, exist_ok=True)

    with brain.get_connection() as conn:
        invariants = query_sorted_invariants(conn)
        decisions = query_sorted_decisions(conn)

    skills = load_skill_index(kit_dir)
    friction = load_friction_log(kit_dir)

    context = {
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "timestamp": now_iso(),
        "limits": {
            "invariants": 10,
            "decisions": 10,
            "skills": 20,
            "friction": 10,
        },
        "invariants": invariants,
        "decisions": decisions,
        "skills": skills,
        "friction": friction,
    }

    # Generate hash AFTER content is finalized
    context["context_hash"] = context_hash(context)

    return context


def save_execution_context(brain) -> Path:
    """Save execution_context.json to .kit/ directory."""
    context = assemble_execution_context(brain)

    kit_dir = brain.root_path / ".kit"
    output_path = kit_dir / "execution_context.json"

    json_str = deterministic_json(context)
    output_path.write_text(json_str, encoding="utf-8")

    return output_path


def verify_context_stability(brain) -> dict[str, Any]:
    """
    Verify context hash is stable across multiple builds.

    Returns:
    {
        "stable": bool,
        "hash": str,
        "runs": int,
    }
    """
    hashes = []
    for _ in range(3):
        context = assemble_execution_context(brain)
        hashes.append(context["context_hash"])

    return {
        "stable": len(set(hashes)) == 1,
        "hash": hashes[0],
        "runs": 3,
    }
