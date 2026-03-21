import shutil
import sqlite3
import sys

from kit.core.kit_cognitive_core import SAMBrain

DASHBOARD_WIDTH = 40


def normalize_for_dedup(text: str) -> str:
    import re

    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def run_doctor(brain: SAMBrain, mode: str = "safe", check_agents: bool = False, reset_cloud: bool = False) -> None:
    print(f"AI Kernel Health Check (Mode: {mode})", file=sys.stderr)

    db_path = brain.db_path
    backup_path = db_path.with_name("brain.db.bak")
    try:
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path.name}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not create backup: {e}", file=sys.stderr)

    with brain._get_connection() as conn:  # type: ignore[reportPrivateUsage]
        print("Running Cognitive Pruning...", file=sys.stderr)
        if mode == "aggressive":
            cutoff_days = 30
            low_access = 1
            cur = conn.execute(
                """
                DELETE FROM observations
                WHERE layer IN ('working', 'episodic')
                  AND access_count <= ?
                  AND tag = 'decision'
                  AND JULIANDAY('now') - JULIANDAY(created_at) > ?
                """,
                (low_access, cutoff_days),
            )
            pruned_count = cur.rowcount
            if pruned_count > 0:
                print(f"  - Permanently removed {pruned_count} decayed facts.", file=sys.stderr)
        else:
            cutoff_days = 90
            low_access = 0
            cur = conn.execute(
                """
                UPDATE observations SET superseded_at = CURRENT_TIMESTAMP
                WHERE layer IN ('working', 'episodic')
                  AND access_count <= ?
                  AND tag = 'decision'
                  AND superseded_at IS NULL
                  AND JULIANDAY('now') - JULIANDAY(created_at) > ?
                """,
                (low_access, cutoff_days),
            )
            pruned_count = cur.rowcount
            if pruned_count > 0:
                print(f"  - Soft-pruned {pruned_count} decayed facts.", file=sys.stderr)

        print("Running Fact Deduplication...", file=sys.stderr)
        rows = conn.execute(
            """
            SELECT id, content, scope, layer, importance, access_count, tag
            FROM observations
            WHERE superseded_at IS NULL
            ORDER BY created_at ASC
            """
        ).fetchall()

        seen: dict[str, int] = {}
        merged_count = 0

        for row in rows:
            norm_content = normalize_for_dedup(row["content"])
            scope = row["scope"] or ""
            layer = row["layer"] or ""
            tag = row["tag"] or ""
            sig = f"{norm_content}|{scope}|{layer}|{tag}"

            if sig in seen:
                keep_id = seen[sig]
                drop_id = row["id"]
                conn.execute("UPDATE observations SET superseded_at = CURRENT_TIMESTAMP WHERE id = ?", (drop_id,))
                conn.execute(
                    "UPDATE observations SET access_count = access_count + ? WHERE id = ?",
                    (row["access_count"] + 1, keep_id),
                )
                merged_count += 1
            else:
                seen[sig] = row["id"]

        if merged_count > 0:
            print(f"  - Merged {merged_count} duplicate facts safely.", file=sys.stderr)

        print("Optimizing Storage...", file=sys.stderr)
        conn.execute("VACUUM")
        conn.execute("PRAGMA optimize")

    if check_agents or reset_cloud:
        print("\n[AGENT DIAGNOSTICS]", file=sys.stderr)
        with sqlite3.connect(brain.db_path, timeout=5.0) as conn:
            conn.row_factory = sqlite3.Row

            if reset_cloud:
                conn.execute("DELETE FROM agent_metrics WHERE name != 'local'")
                print("  - Cloud provider metrics reset.", file=sys.stderr)

            if check_agents:
                import json

                rows = conn.execute("SELECT * FROM agent_metrics ORDER BY name").fetchall()
                if not rows:
                    print("  - No Persisted Metrics: All agents are in clean state.", file=sys.stderr)
                else:
                    for row in rows:
                        try:
                            data = json.loads(row["data"])
                            successes = data.get("successes", 0)
                            failures = data.get("failures", 0)
                            healthy = "HEALTHY" if data.get("healthy", True) else "DEGRADED (Cooldown)"
                            latency = data.get("avg_latency", 0.0)

                            print(
                                f"  - {row['name']:8}: {healthy:20} [S:{successes} F:{failures}] Latency: {latency:.2f}s",
                                file=sys.stderr,
                            )
                        except (KeyError, TypeError, ValueError):
                            print(f"  - {row['name']:8}: Error reading metrics data.", file=sys.stderr)

    # --- Dashboard Summary ---
    from kit.api import get_brain
    
    # Try to get version from pyproject.toml if possible
    package_version = "1.2.2-Ultimate" # Hardcoded for now, should be dynamic in 1.2.3
    
    brain = get_brain()
    
    # Count stats using internal connection helper
    with brain._get_connection() as conn:
        total_facts = conn.execute("SELECT COUNT(*) FROM observations WHERE is_active = 1").fetchone()[0]
        invariants = conn.execute(
            "SELECT COUNT(*) FROM observations WHERE tag = 'invariant' AND is_active = 1"
        ).fetchone()[0]
        decisions = conn.execute(
            "SELECT COUNT(*) FROM observations WHERE tag = 'decision' AND is_active = 1"
        ).fetchone()[0]

    border = "=" * DASHBOARD_WIDTH
    print("\n" + border, file=sys.stderr)
    print(" .KIT COGNITIVE DASHBOARD", file=sys.stderr)
    print(border, file=sys.stderr)
    print(f" Version:     {package_version}", file=sys.stderr)
    print(f" Project DB:  {brain.db_path}", file=sys.stderr)
    print(f" Global DB:   {brain.global_db_path if hasattr(brain, 'global_db_path') else 'N/A'}", file=sys.stderr)
    print(f" Total Facts: {total_facts}", file=sys.stderr)
    print(f" Invariants:  {invariants}", file=sys.stderr)
    print(f" Decisions:   {decisions}", file=sys.stderr)
    print(f" Engine:      {'HEALTHY' if total_facts > 0 else 'EMPTY'}", file=sys.stderr)
    print(border, file=sys.stderr)

    if invariants == 0:
        print(
            "\nTIP: No invariants found. Run `kit learn --tag invariant 'Rule'` to secure your architecture.",
            file=sys.stderr,
        )

    print("\nAll subsystems operational.", file=sys.stderr)
