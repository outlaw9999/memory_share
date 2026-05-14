import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kit.core.deterministic import deterministic_json, stable_hash

SCHEMA_VERSION = "1.0"
RUNTIME_VERSION = "1.2.5"


def load_friction_log(kit_dir: Path) -> dict[str, list]:
    friction_file = kit_dir / "friction.json"
    if not friction_file.exists():
        return {"active": [], "resolved": []}
    try:
        data = json.loads(friction_file.read_text(encoding="utf-8"))
        if "active" not in data or "resolved" not in data:
            return {"active": [], "resolved": []}
        return data
    except Exception:
        return {"active": [], "resolved": []}


def compile_execution_context(brain) -> dict[str, Any]:
    """
    Assemble the complete deterministic execution context from the Kit brain.
    """
    limit_invariants = 10
    limit_decisions = 10

    from kit.core.memory_policy import MemoryPolicy

    # 1. Query invariants safely and deterministically
    with brain.get_connection() as conn:
        invariants = []
        sql_inv = f"""
            {MemoryPolicy.SQL_RECALL_BASE}
            AND o.tag = 'invariant'
            ORDER BY o.importance DESC, o.created_at ASC, n.uid ASC, o.id ASC
            LIMIT {limit_invariants}
        """
        for r in conn.execute(sql_inv).fetchall():
            invariants.append(
                {
                    "uid": r["uid"].upper(),
                    "id": r["id"],
                    "importance": r["importance"],
                    "created_at": r["created_at"],
                    "content": r["content"],
                }
            )

        # 2. Query decisions
        decisions = []
        sql_dec = f"""
            {MemoryPolicy.SQL_RECALL_BASE}
            AND o.tag = 'decision'
            ORDER BY o.importance DESC, o.created_at ASC, n.uid ASC, o.id ASC
            LIMIT {limit_decisions}
        """
        for r in conn.execute(sql_dec).fetchall():
            decisions.append(
                {
                    "uid": r["uid"].upper(),
                    "id": r["id"],
                    "importance": r["importance"],
                    "created_at": r["created_at"],
                    "content": r["content"],
                }
            )

    # 3. Load skills (Assuming the procedural skill matcher can return dicts)
    from kit.skills.matcher import list_procedural_skills

    raw_skills = list_procedural_skills()
    skills = []

    # Deterministic sorting for skills by name
    raw_skills.sort(key=lambda s: s.get("name", "z"))

    for s in raw_skills[:20]:  # Limit 20
        skills.append(
            {
                "name": s.get("name", "unknown"),
                "triggers": sorted(s.get("triggers", [])),  # ensure sorted
                "deterministic": bool(s.get("deterministic", True)),
                "safety_level": s.get("safety_level", "unknown"),
                "side_effect": s.get("side_effect", "none"),
            }
        )

    # 4. Friction log
    kit_dir = brain.root_path / ".kit"
    friction = load_friction_log(kit_dir)

    # Optionally sort the friction lists for determinism
    friction["active"].sort()
    friction["resolved"].sort()

    # 5. Assemble structure
    current_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    context = {
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "timestamp": current_time,
        "context_hash": "",  # placeholder
        "limits": {"invariants": limit_invariants, "decisions": limit_decisions, "skills": 20, "friction": 10},
        "invariants": invariants,
        "decisions": decisions,
        "skills": skills,
        "friction": friction,
    }

    # Generate Blake2b hash
    del context["context_hash"]
    del context["timestamp"]
    sig = deterministic_json(context)
    context["context_hash"] = stable_hash(sig)
    context["timestamp"] = current_time

    # Return ordered exactly like schema
    final_context = {
        "schema_version": context["schema_version"],
        "runtime_version": context["runtime_version"],
        "timestamp": context["timestamp"],
        "context_hash": context["context_hash"],
        "limits": context["limits"],
        "invariants": context["invariants"],
        "decisions": context["decisions"],
        "skills": context["skills"],
        "friction": context["friction"],
    }

    return final_context


def save_execution_context(brain) -> Path:
    context_data = compile_execution_context(brain)

    kit_dir = brain.root_path / ".kit"
    kit_dir.mkdir(parents=True, exist_ok=True)

    out_path = kit_dir / "execution_context.json"

    json_str = deterministic_json(context_data)
    out_path.write_text(json_str, encoding="utf-8")

    return out_path
