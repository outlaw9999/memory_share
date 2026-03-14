#!/usr/bin/env python3
"""
antigravity_mcp — MCP server for the Antigravity brain v2 memory system.

Exposes 5 tools for any MCP-compatible agent (Claude, Cursor, etc.):
  brain_query       — semantic search Layer 3 memory
  brain_remember    — write a new memory to layer1_stream
  brain_search_text — fast full-text search across layer2_core (no DB needed)
  brain_status      — workspace health check and DB statistics
  brain_maintain    — run background consolidation (dry-run or live)

Transport: stdio (local use)
Python: 3.10+  (no neural-memory required for query/write/status)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server init
# ---------------------------------------------------------------------------

mcp = FastMCP("antigravity_mcp")

# ---------------------------------------------------------------------------
# Workspace resolution
# ---------------------------------------------------------------------------


def _workspace() -> Path:
    root = os.environ.get("ANTIGRAVITY_WORKSPACE_ROOT")
    if root:
        return Path(root).resolve()
    # Default: two directories above this file (brain/mcp/ -> brain/ -> root)
    return Path(__file__).resolve().parent.parent.parent


def _db_path() -> Path:
    return _workspace() / "brain" / "layer3_index" / "neural_memory.db"


def _ops_dir() -> Path:
    # Scripts live in brain/ops/ relative to the REPO root (2 dirs above brain/mcp/)
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / "brain" / "ops"


def _stream_dir() -> Path:
    return _workspace() / "brain" / "layer1_stream"


def _core_dir() -> Path:
    return _workspace() / "brain" / "layer2_core"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _slugify(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower())
    return re.sub(r"_+", "_", clean).strip("_") or "unknown"


def _today_stream_path(project: str) -> Path:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    if project and project.lower() not in {"root", "global", "workspace"}:
        target = _stream_dir() / "projects" / _slugify(project)
    else:
        target = _stream_dir()
    target.mkdir(parents=True, exist_ok=True)
    return target / f"{date_str}.md"


def _db_stats(conn: sqlite3.Connection) -> dict:
    counts = {}
    for table in ("brains", "neurons", "fibers", "synapses"):
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0] if row else 0
        except Exception:
            counts[table] = "n/a"
    return counts


# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------


class QueryInput(BaseModel):
    """Input for brain_query."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Free-text search query (e.g. 'API login bug', 'deployment steps')",
        min_length=2,
        max_length=300,
    )
    project: Optional[str] = Field(
        default=None,
        description="Filter by project name or slug (e.g. 'my_project')",
        max_length=100,
    )
    scope: Optional[str] = Field(
        default=None,
        description="Filter by scope: 'workspace' or 'project'",
        pattern=r"^(workspace|project)$",
    )
    include_private: bool = Field(
        default=False,
        description="Include private memories (default: false)",
    )
    limit: int = Field(
        default=5,
        description="Maximum number of results to return (1–20)",
        ge=1,
        le=20,
    )
    response_format: str = Field(
        default="markdown",
        description="Output format: 'markdown' (default) or 'json'",
        pattern=r"^(markdown|json)$",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class RememberInput(BaseModel):
    """Input for brain_remember."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    content: str = Field(
        ...,
        description="Memory content in Markdown. Use headers (##) to add structure.",
        min_length=10,
        max_length=10000,
    )
    heading: str = Field(
        ...,
        description="Short heading for this memory (e.g. 'API Login Fix')",
        min_length=2,
        max_length=120,
    )
    project: str = Field(
        default="Root",
        description="Project name this memory belongs to (e.g. 'my_project'). Use 'Root' for workspace-level.",
        max_length=100,
    )
    privacy: str = Field(
        default="restricted",
        description="Privacy level: 'shareable', 'restricted' (default), or 'private'",
        pattern=r"^(shareable|restricted|private)$",
    )


class SearchTextInput(BaseModel):
    """Input for brain_search_text."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Text to search for across layer2_core Markdown files",
        min_length=2,
        max_length=200,
    )
    include_stream: bool = Field(
        default=False,
        description="Also search layer1_stream recent logs (last 5 files)",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of matching lines to return",
        ge=1,
        le=50,
    )


class MaintainInput(BaseModel):
    """Input for brain_maintain."""

    model_config = ConfigDict(extra="forbid")

    dry_run: bool = Field(
        default=True,
        description="If true (default), report changes without writing. Set false to apply.",
    )
    stale_days: int = Field(
        default=30,
        description="Age threshold in days for stale memory classification",
        ge=1,
        le=365,
    )


# ---------------------------------------------------------------------------
# Tool: brain_query
# ---------------------------------------------------------------------------


@mcp.tool(
    name="brain_query",
    annotations={
        "title": "Query Antigravity Brain Memory",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_query(params: QueryInput) -> str:
    """Search Layer 3 semantic memory index for relevant context.

    Queries the local SQLite neural memory index using full-text search
    plus re-ranking by activation level, access frequency, and freshness.
    Returns the most relevant memory chunks for the given query.

    Use this tool FIRST when you need context about a project, past decisions,
    bug fixes, or any domain knowledge the user has previously stored.

    Args:
        params (QueryInput):
            - query (str): Free-text search query (required)
            - project (Optional[str]): Filter by project name
            - scope (Optional[str]): 'workspace' or 'project'
            - include_private (bool): Include private memories (default: false)
            - limit (int): Max results 1–20 (default: 5)
            - response_format (str): 'markdown' or 'json' (default: 'markdown')

    Returns:
        str: Formatted memory results, or "No memories found" if empty.

    Examples:
        - "What do I know about the API login bug?" → query="API login bug"
        - "Recall deployment steps for project X" → query="deployment", project="X"
        - "Get all workspace-level memories about Python" → query="Python", scope="workspace"
    """
    db = _db_path()
    if not db.exists():
        return (
            "Error: Layer 3 database not found. "
            "Run `python setup_workspace.py` to initialize, then run "
            "`brain_sync_watcher.py` to index your memory files."
        )

    try:
        # Build FTS terms
        terms = re.findall(r"[A-Za-z0-9_]+", params.query.lower())
        if not terms:
            return "Error: Query contains no searchable terms."
        fts_query = " AND ".join(terms)

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        sql = (
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
        sql_params: list = [fts_query]

        if params.project:
            slug = _slugify(params.project)
            sql += (
                " AND (json_extract(n.metadata, '$.project') = ? "
                "OR json_extract(n.metadata, '$.project_slug') = ?)"
            )
            sql_params.extend([params.project, slug])

        if params.scope:
            sql += " AND json_extract(n.metadata, '$.scope') = ?"
            sql_params.append(params.scope)

        if not params.include_private:
            sql += " AND COALESCE(json_extract(n.metadata, '$.privacy'), 'shareable') != 'private'"

        sql += f" ORDER BY text_score DESC LIMIT ?"
        sql_params.append(params.limit * 5)

        rows = conn.execute(sql, sql_params).fetchall()
        conn.close()

        if not rows:
            return f"No memories found for query: '{params.query}'"

        # Re-rank
        results = []
        now = datetime.now(UTC)
        for row in rows:
            meta = json.loads(row["metadata"] or "{}")
            ts_str = (
                meta.get("indexed_at")
                or meta.get("source_timestamp")
                or row["created_at"]
            )
            freshness = 0.0
            try:
                dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
                freshness = max(0.0, 30.0 - age_days) * 0.01
            except Exception:
                pass
            score = float(row["text_score"]) + float(row["access_frequency"]) * 0.1
            score += float(row["activation_level"]) * 0.5 + freshness
            results.append(
                {
                    "score": round(score, 4),
                    "content": row["content"],
                    "metadata": meta,
                    "brain": row["brain_name"],
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[: params.limit]

        if params.response_format == "json":
            return json.dumps(results, indent=2, ensure_ascii=False)

        # Markdown output
        lines = [
            f"## Brain Memory: '{params.query}'\n",
            f"*{len(results)} result(s) found*\n",
        ]
        for i, item in enumerate(results, 1):
            meta = item["metadata"]
            heading = meta.get("source_heading") or "(no heading)"
            source = meta.get("source_path") or meta.get("source") or "unknown"
            project = meta.get("project", "unknown")
            privacy = meta.get("privacy", "unknown")
            snippet = (
                str(item["content"]).replace("\ufeff", "").replace("\n", " ").strip()
            )
            lines.append(f"### [{i}] {heading}")
            lines.append(
                f"- **Project**: {project} | **Privacy**: {privacy} | **Score**: {item['score']}"
            )
            lines.append(f"- **Source**: `{source}`")
            lines.append(
                f"- **Content**: {snippet[:300]}{'...' if len(snippet) > 300 else ''}"
            )
            lines.append("")
        return "\n".join(lines)

    except sqlite3.OperationalError as e:
        return f"Error: Database query failed — {e}. The DB schema may be outdated. Run `setup_workspace.py`."
    except Exception as e:
        return f"Error: Unexpected error during query — {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Tool: brain_remember
# ---------------------------------------------------------------------------


@mcp.tool(
    name="brain_remember",
    annotations={
        "title": "Store New Memory in Brain",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def brain_remember(params: RememberInput) -> str:
    """Write a new memory entry to layer1_stream for indexing.

    Appends a structured Markdown block to today's stream log file for the
    given project. The entry will be automatically picked up and indexed into
    Layer 3 by brain_sync_watcher on its next cycle.

    Use this tool to persist important decisions, bug fixes, notes, or any
    information that should be retrievable in future sessions.

    Args:
        params (RememberInput):
            - content (str): Memory content in Markdown (required)
            - heading (str): Short heading for this memory (required)
            - project (str): Project name (default: 'Root')
            - privacy (str): 'shareable', 'restricted' (default), or 'private'

    Returns:
        str: Confirmation message with file path, or error description.

    Examples:
        - Store a bug fix: heading="API Login Fix", content="Fixed by adding retry..."
        - Log a decision: heading="Use FastAPI over Flask", content="Decision: ...", project="backend"
    """
    try:
        stream_path = _today_stream_path(params.project)
        timestamp = datetime.now(UTC).strftime("%H:%M UTC")
        privacy_tag = f"privacy: {params.privacy}"

        block = (
            f"\n## {params.heading}\n\n"
            f"<!-- {privacy_tag} | {timestamp} -->\n\n"
            f"{params.content.strip()}\n"
        )

        with open(stream_path, "a", encoding="utf-8") as f:
            # Write frontmatter if file is new
            if stream_path.stat().st_size == 0:
                date_str = datetime.now(UTC).strftime("%Y-%m-%d")
                f.write(f"---\ndate: {date_str}\nproject: {params.project}\n---\n")
            f.write(block)

        rel = str(stream_path.relative_to(_workspace()))
        return (
            f"Memory stored in `{rel}`\n\n"
            f"**Heading**: {params.heading}\n"
            f"**Project**: {params.project} | **Privacy**: {params.privacy}\n\n"
            f"It will be indexed into Layer 3 on the next `brain_sync_watcher` cycle.\n"
            f"Run `brain_sync_watcher.py` manually to index immediately."
        )
    except Exception as e:
        return f"Error: Failed to write memory — {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Tool: brain_search_text
# ---------------------------------------------------------------------------


@mcp.tool(
    name="brain_search_text",
    annotations={
        "title": "Fast Text Search Across Brain Files",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_search_text(params: SearchTextInput) -> str:
    """Fast full-text grep across layer2_core Markdown files. No DB required.

    Searches layer2_core Markdown files directly using string matching.
    Much faster than brain_query for simple keyword lookups when you don't
    need semantic ranking. Optionally also searches recent layer1_stream logs.

    Use this tool when:
    - You need a quick check for a specific term or phrase
    - Layer 3 DB is not yet indexed
    - You want to confirm a keyword exists before a semantic query

    Args:
        params (SearchTextInput):
            - query (str): Text to search for (required)
            - include_stream (bool): Also search layer1_stream (default: false)
            - limit (int): Max matching lines to return 1–50 (default: 10)

    Returns:
        str: Matching lines with file context, or "No matches found".
    """
    try:
        results: list[str] = []
        pattern = re.compile(re.escape(params.query), re.IGNORECASE)

        def _scan_dir(
            directory: Path, label: str, file_limit: Optional[int] = None
        ) -> None:
            if not directory.exists():
                return
            md_files = sorted(
                directory.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if file_limit:
                md_files = md_files[:file_limit]
            for fp in md_files:
                try:
                    rel = fp.relative_to(_workspace())
                    for lineno, line in enumerate(
                        fp.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                    ):
                        if pattern.search(line):
                            results.append(f"`{rel}:{lineno}` — {line.strip()[:150]}")
                            if len(results) >= params.limit:
                                return
                except Exception:
                    pass

        _scan_dir(_core_dir(), "layer2_core")
        if params.include_stream and len(results) < params.limit:
            _scan_dir(_stream_dir(), "layer1_stream", file_limit=5)

        if not results:
            return f"No matches found for '{params.query}' in layer2_core{'+ layer1_stream' if params.include_stream else ''}."

        lines = [f"## Text Search: '{params.query}'\n", f"*{len(results)} match(es)*\n"]
        lines.extend(f"- {r}" for r in results)
        return "\n".join(lines)

    except Exception as e:
        return f"Error: Text search failed — {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Tool: brain_status
# ---------------------------------------------------------------------------


@mcp.tool(
    name="brain_status",
    annotations={
        "title": "Antigravity Brain Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_status() -> str:
    """Return workspace health check and Layer 3 database statistics.

    Shows current workspace configuration, directory structure status,
    DB record counts, and whether the brain is ready to use.

    Use this tool to:
    - Verify the brain is properly set up before querying
    - Check how many memories are indexed
    - Debug workspace path issues

    Returns:
        str: Markdown status report with workspace info and DB stats.
    """
    ws = _workspace()
    db = _db_path()

    layers = {
        "layer1_stream": ws / "brain" / "layer1_stream",
        "layer2_core": ws / "brain" / "layer2_core",
        "layer2_private": ws / "brain" / "layer2_private",
        "layer3_index": ws / "brain" / "layer3_index",
    }

    lines = ["## Antigravity Brain Status\n"]
    lines.append(f"**Workspace**: `{ws}`")
    lines.append(f"**DB path**: `{db}`\n")

    lines.append("### Directory Structure")
    for name, path in layers.items():
        exists = "✅" if path.exists() else "❌ missing"
        md_count = len(list(path.rglob("*.md"))) if path.exists() else 0
        lines.append(
            f"- `{name}`: {exists}{f' — {md_count} .md files' if path.exists() else ''}"
        )

    lines.append("\n### Layer 3 Database")
    if not db.exists():
        lines.append(
            "❌ Database not found. Run `python setup_workspace.py` to initialize."
        )
    else:
        try:
            conn = sqlite3.connect(str(db))
            stats = _db_stats(conn)
            conn.close()
            lines.append(f"✅ Database exists ({db.stat().st_size // 1024} KB)")
            for table, count in stats.items():
                lines.append(f"- `{table}`: {count} records")
        except Exception as e:
            lines.append(f"⚠ Could not read database: {e}")

    lines.append("\n### Readiness")
    db_ok = db.exists()
    stream_ok = layers["layer1_stream"].exists()
    lines.append(f"- DB initialized: {'✅' if db_ok else '❌'}")
    lines.append(f"- layer1_stream ready: {'✅' if stream_ok else '❌'}")
    if db_ok and stream_ok:
        lines.append(
            "\n✅ Brain is ready. Start `brain_sync_watcher.py` to enable live indexing."
        )
    else:
        lines.append("\n❌ Run `python setup_workspace.py` to complete setup.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: brain_maintain
# ---------------------------------------------------------------------------


@mcp.tool(
    name="brain_maintain",
    annotations={
        "title": "Run Brain Maintenance",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_maintain(params: MaintainInput) -> str:
    """Run the Layer 3 background consolidation job.

    Classifies all anchor memories as promotion candidates, duplicates,
    stale, or hot/warm/cold. In dry-run mode (default), only reports what
    would change. Set dry_run=false to apply changes and write the digest.

    Phase 3 maintenance is non-destructive: no neurons are deleted.

    Args:
        params (MaintainInput):
            - dry_run (bool): Report only, no writes (default: true)
            - stale_days (int): Age threshold for stale classification (default: 30)

    Returns:
        str: Summary of maintenance results or error description.
    """
    ops = _ops_dir()
    maintenance_script = ops / "brain_maintenance.py"

    if not maintenance_script.exists():
        return f"Error: Maintenance script not found at `{maintenance_script}`. Check ANTIGRAVITY_WORKSPACE_ROOT."

    db = _db_path()
    if not db.exists():
        return "Error: Layer 3 DB not found. Run `setup_workspace.py` first."

    cmd = [sys.executable, str(maintenance_script), f"--stale-days={params.stale_days}"]
    if params.dry_run:
        cmd.append("--dry-run")

    env = {**os.environ, "ANTIGRAVITY_WORKSPACE_ROOT": str(_workspace())}

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=60
        )
        output = result.stdout.strip() or result.stderr.strip()
        mode = "DRY RUN" if params.dry_run else "APPLIED"
        return f"## Brain Maintenance ({mode})\n\n```\n{output}\n```"
    except subprocess.TimeoutExpired:
        return "Error: Maintenance job timed out after 60 seconds."
    except Exception as e:
        return f"Error: Failed to run maintenance — {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
