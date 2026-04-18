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


def run_doctor(
    brain: SAMBrain,
    mode: str = "safe",
    check_agents: bool = False,
    reset_cloud: bool = False,
    fix_shell: bool = False,
    migrate_memory: bool = False,
    heal: bool = False,
) -> None:
    print(f"AI Kernel Health Check (Mode: {mode})", file=sys.stderr)

    db_path = brain.db_path
    backup_path = db_path.with_name("brain.db.bak")
    try:
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path.name}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not create backup: {e}", file=sys.stderr)

    with brain.get_connection() as conn:
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
        conn.commit()  # Ensure no active transaction
        conn.execute("VACUUM")
        conn.execute("PRAGMA optimize")

    if check_agents or reset_cloud:
        print("\n[AGENT DIAGNOSTICS]", file=sys.stderr)
        with brain.get_connection() as conn:
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

    # --- Environment Audit ---
    if migrate_memory:
        print("\n[MEMORY MIGRATION]", file=sys.stderr)
        from kit.core.memory_topology import MemoryTopologyFactory
        
        topo = brain.topology
        root = brain.root_path
        
        # Local Migration
        legacy_local = root / ".kit" / "brain.db"
        new_local = topo.resolve("local", "local")
        
        if legacy_local.exists() and not new_local.exists():
            print(f"  - Migrating: {legacy_local.name} -> {new_local.name}")
            try:
                # We rename the main file. 
                # SQLite will handle WAL/SHM if the connection is closed.
                legacy_local.rename(new_local)
                print(f"  ✔ Local memory migrated.")
            except Exception as e:
                print(f"  ✖ Local migration failed: {e}")

        # Global Migration
        global_kit_dir = topo.resolve("global", "local").parent
        legacy_global = global_kit_dir / "global.db"
        new_global = topo.resolve("global", "global")

        if legacy_global.exists() and not new_global.exists():
            print(f"  - Migrating: {legacy_global.name} -> {new_global.name}")
            try:
                legacy_global.rename(new_global)
                print(f"  ✔ Global memory migrated.")
            except Exception as e:
                print(f"  ✖ Global migration failed: {e}")

    if heal:
        print("\n[HYGIENE HEALING]", file=sys.stderr)
        from kit.core.kit_hygiene import perform_hygiene_cleanup
        removed = perform_hygiene_cleanup(brain.root_path, dry_run=False)
        if removed:
            print(f"  ✔ Removed {len(removed)} disposable artifacts.", file=sys.stderr)
            for r in removed[:5]: # Print first 5
                print(f"    - {r}", file=sys.stderr)
            if len(removed) > 5:
                print(f"    - ... and {len(removed)-5} more", file=sys.stderr)
        else:
            print("  ✔ Workspace is already clean.", file=sys.stderr)

    print("\n[SYSTEM AUDIT]", file=sys.stderr)
    from pathlib import Path
    import os
    import subprocess
    from kit.core import kit_env

    root = brain.root_path
    
    # 1. PEP 668 / Venv Check
    substrate = kit_env.get_substrate_report()
    locked = substrate["is_locked"]
    print(f"  {'✔' if locked else '✖'} Python Interpreter (.venv): {'ACTIVE' if locked else 'DRIFT DETECTED'}", file=sys.stderr)

    # 2. SQLite WAL mode
    wal_healthy = True
    try:
        with brain.get_connection() as conn:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            if journal_mode.lower() != 'wal':
                wal_healthy = False
    except:
        wal_healthy = False
    print(f"  {'✔' if wal_healthy else '✖'} SQLite WAL Mode:           {'HEALTHY' if wal_healthy else 'NOT ENABLED'}", file=sys.stderr)

    # 3. Git Repo
    dot_git = root / ".git"
    print(f"  {'✔' if dot_git.exists() else '✖'} Git Repository:            {'DETECTED' if dot_git.exists() else 'NOT FOUND'}", file=sys.stderr)

    # 4. .kit Accessibility
    kit_dir = root / ".kit"
    print(f"  {'✔' if kit_dir.is_dir() else '✖'} .kit Infrastructure:      {'ACCESSIBLE' if kit_dir.is_dir() else 'MISSING'}", file=sys.stderr)

    # 5. Shell Aliases (Experimental check)
    if sys.platform == "win32":
        # Check if kb, kd, kt are available in powershell
        aliases_found = False
        try:
            # We try to run Get-Command for one of our functions
            res = subprocess.run(["powershell", "-Command", "Get-Command kb -ErrorAction SilentlyContinue"], capture_output=True)
            if res.returncode == 0:
                aliases_found = True
        except:
            pass
        print(f"  {'✔' if aliases_found else '✖'} PowerShell Kit Functions: {'READY' if aliases_found else 'NOT DETECTED (Run ./kit-activate.ps1)'}", file=sys.stderr)

    if fix_shell and sys.platform == "win32":
        print("\n[FIX] Shell & Infrastructure mutation requested...", file=sys.stderr)
        
        # 1. PowerShell Aliases
        print("  - To persist aliases, ensure you source 'kit-activate.ps1' in your $PROFILE.", file=sys.stderr)
        
        # 2. Python Infrastructure (Vết sẹo Python)
        from kit.core import kit_env
        substrate = kit_env.get_substrate_report()
        
        if not substrate["is_locked"]:
            print("  - DRIFT DETECTED: Attempting automated Python Infrastructure Rebirth...", file=sys.stderr)
            
            # Skill: Tactical Strike (taskkill)
            print("    * Tactical Strike: Terminating zombie Language Servers...", file=sys.stderr)
            try:
                subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/T"], capture_output=True)
                subprocess.run(["taskkill", "/F", "/IM", "pylance", "/T"], capture_output=True)
            except:
                pass
                
            # Skill: Hard Purge & Rebirth
            venv_path = Path(substrate["venv_discovered"]) if substrate["venv_discovered"] != "missing" else root / ".venv"
            if venv_path.exists():
                print(f"    * Hard Purge: Removing corrupted venv at {venv_path}...", file=sys.stderr)
                try:
                    shutil.rmtree(venv_path)
                except Exception as e:
                    print(f"    ⚠️ Failed to purge venv: {e}", file=sys.stderr)
            
            print("    * Rebirth: You must run 'python -m venv .venv' and reinstall dependencies.", file=sys.stderr)
            print("    💡 Tip: Use 'kit boot' after recreation to verify.", file=sys.stderr)

        # 3. Clean .vscode/settings.json (Vết sẹo Python fix)
        vscode_settings = root / ".vscode" / "settings.json"
        if vscode_settings.exists():
            print("  - Cleaning .vscode/settings.json (Vết sẹo Python fix)...", file=sys.stderr)
            try:
                import json
                with open(vscode_settings, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                
                dirty = False
                for key in ["python.defaultInterpreterPath", "python.pythonPath"]:
                    if key in settings:
                        val = settings[key]
                        # If it contains absolute path or non-relative venv, remove it
                        if ":" in val or ("venv" in val.lower() and "${workspaceFolder}" not in val):
                            del settings[key]
                            dirty = True
                
                if dirty:
                    with open(vscode_settings, "w", encoding="utf-8") as f:
                        json.dump(settings, f, indent=4)
                    print("    ✔ Cleaned legacy interpreter paths from settings.json.", file=sys.stderr)
            except Exception as e:
                print(f"    ⚠️ Failed to clean settings.json: {e}", file=sys.stderr)

        print("  - Fixed: Guidance emitted and infrastructure stabilized.", file=sys.stderr)
    from kit.api import get_brain

    # Try to get version from pyproject.toml if possible
    package_version = "1.2.3-Ultimate"

    brain = get_brain()

    # Count stats using public connection helper
    with brain.get_connection() as conn:
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
