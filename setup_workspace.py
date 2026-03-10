"""
setup_workspace.py — One-time workspace initializer for Antigravity brain v2.

Run once before starting brain_sync_watcher.py for the first time.
Creates the required directory structure and sets up the Layer 3 SQLite schema.

Usage:
    py -3 setup_workspace.py
    py -3 setup_workspace.py --workspace /path/to/your/workspace
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import UTC, datetime


DIRS = [
    "brain/layer1_stream",
    "brain/layer2_core",
    "brain/layer2_private",
    "brain/layer3_index",
    "brain/ops",
]

GITKEEP_DIRS = [
    "brain/layer1_stream",
    "brain/layer2_core",
    "brain/layer3_index",
]

LAYER2_GITIGNORE = """\
# Managed by Antigravity — do not edit manually
*.db
*.db.*
.sync_state.json
"""

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS brains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    config TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS neurons (
    id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    PRIMARY KEY (brain_id, id),
    FOREIGN KEY (brain_id) REFERENCES brains(id)
);

CREATE TABLE IF NOT EXISTS neuron_states (
    brain_id TEXT NOT NULL,
    neuron_id TEXT NOT NULL,
    activation_level REAL NOT NULL DEFAULT 0.0,
    access_frequency INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TEXT,
    PRIMARY KEY (brain_id, neuron_id),
    FOREIGN KEY (brain_id, neuron_id) REFERENCES neurons(brain_id, id)
);

CREATE TABLE IF NOT EXISTS fibers (
    id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    anchor_neuron_id TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    PRIMARY KEY (brain_id, id),
    FOREIGN KEY (brain_id) REFERENCES brains(id)
);

CREATE TABLE IF NOT EXISTS synapses (
    brain_id TEXT NOT NULL,
    source_neuron_id TEXT NOT NULL,
    target_neuron_id TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (brain_id, source_neuron_id, target_neuron_id),
    FOREIGN KEY (brain_id) REFERENCES brains(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS neurons_fts USING fts5(
    content,
    content='neurons',
    content_rowid='rowid'
);

CREATE INDEX IF NOT EXISTS idx_neurons_brain_id ON neurons(brain_id);
CREATE INDEX IF NOT EXISTS idx_fibers_anchor ON fibers(brain_id, anchor_neuron_id);
CREATE INDEX IF NOT EXISTS idx_synapses_source ON synapses(brain_id, source_neuron_id);
CREATE INDEX IF NOT EXISTS idx_neuron_states ON neuron_states(brain_id, neuron_id);
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize Antigravity brain v2 workspace.")
    parser.add_argument(
        "--workspace",
        default=os.environ.get("ANTIGRAVITY_WORKSPACE_ROOT", os.getcwd()),
        help="Workspace root path (default: $ANTIGRAVITY_WORKSPACE_ROOT or current directory)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without writing")
    return parser.parse_args()


def create_dirs(workspace: str, dry_run: bool) -> None:
    for rel_dir in DIRS:
        full_path = os.path.join(workspace, rel_dir)
        if not os.path.exists(full_path):
            print(f"  mkdir  {rel_dir}")
            if not dry_run:
                os.makedirs(full_path, exist_ok=True)
        else:
            print(f"  exists {rel_dir}")

    for rel_dir in GITKEEP_DIRS:
        gitkeep = os.path.join(workspace, rel_dir, ".gitkeep")
        if not os.path.exists(gitkeep):
            print(f"  touch  {rel_dir}/.gitkeep")
            if not dry_run:
                open(gitkeep, "w").close()


def create_schema(workspace: str, dry_run: bool) -> None:
    db_path = os.path.join(workspace, "brain", "layer3_index", "neural_memory.db")
    if os.path.exists(db_path):
        print(f"  exists brain/layer3_index/neural_memory.db")
        return
    print(f"  create brain/layer3_index/neural_memory.db")
    if dry_run:
        return
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def write_env_reminder(workspace: str, dry_run: bool) -> None:
    env_path = os.path.join(workspace, ".env.example")
    if not os.path.exists(env_path):
        return
    print(f"\nReminder: copy .env.example to .env and set ANTIGRAVITY_WORKSPACE_ROOT")


def main() -> int:
    args = parse_args()
    workspace = os.path.abspath(args.workspace)

    print(f"Workspace: {workspace}")
    if args.dry_run:
        print("(dry run — no changes will be written)\n")
    else:
        print()

    print("Creating directory structure...")
    create_dirs(workspace, args.dry_run)

    print("\nInitializing Layer 3 SQLite schema...")
    create_schema(workspace, args.dry_run)

    write_env_reminder(workspace, args.dry_run)

    print(f"\n{'[dry run] ' if args.dry_run else ''}Setup complete.")
    print("Next steps:")
    print("  1. Set ANTIGRAVITY_WORKSPACE_ROOT in your environment or .env")
    print("  2. pip install -r requirements.txt  (Python >= 3.11 required)")
    print("  3. py -3 brain/ops/brain_sync_watcher.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
