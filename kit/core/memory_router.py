import hashlib
import json
import logging
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("kit.router")


@dataclass
class WorkspaceId:
    """Hybrid workspace identity for scoped memory isolation."""

    id: str
    git_root_hash: str
    origin_url: str
    created_at: str

    @staticmethod
    def compute(root_path: Path, stable_salt: str = "kit.v124") -> WorkspaceId:
        git_root_hash = WorkspaceId._get_git_root_hash(root_path)
        origin_url = WorkspaceId._get_origin_url(root_path)

        stable_input = f"{git_root_hash}{origin_url}{stable_salt}".encode()
        workspace_id = hashlib.sha256(stable_input).hexdigest()[:16]

        return WorkspaceId(
            id=workspace_id,
            git_root_hash=git_root_hash,
            origin_url=origin_url,
            created_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _get_git_root_hash(root_path: Path) -> str:
        """Fingerprint repo content using git ls-files (not abs_path)."""
        try:
            result = subprocess.run(
                ["git", "ls-files", "-s"],
                cwd=root_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                content_hash = hashlib.sha1(result.stdout.encode()).hexdigest()[:12]
                return content_hash
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return hashlib.sha1(str(root_path).encode()).hexdigest()[:12]

    @staticmethod
    def _get_origin_url(root_path: Path) -> str:
        """Get stable origin URL or empty string if no remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=root_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return ""


class MemoryRouter:
    """
    Dual-write engine for migration from attach_global to attach_scoped.

    Phase 1: Write both GLOBAL and SCOPED (legacy fallback mode)
    Phase 2: Backfill legacy memory to scoped format
    Phase 3: Cutover to SCOPED-only mode
    """

    MIGRATION_PHASE = 2

    def __init__(
        self,
        root_path: Path,
        db_path: Path | None = None,
        global_db_path: Path | None = None,
    ) -> None:
        self.root_path = root_path
        self.db_path = db_path or (root_path / ".kit" / "brain.db")
        self.global_db_path = global_db_path
        self.workspace_id = WorkspaceId.compute(root_path)

    def get_connection(self, db_path: Path | None = None) -> sqlite3.Connection:
        """Create WAL-enabled connection."""
        target = db_path or self.db_path
        conn = sqlite3.connect(
            str(target),
            check_same_thread=False,
            isolation_level=None,
            timeout=5000,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def ensure_workspace_id(self, conn: sqlite3.Connection) -> None:
        """Add workspace_id column to observations if missing."""
        try:
            conn.execute("ALTER TABLE observations ADD COLUMN workspace_id TEXT")
            logger.info("Migrated: Added workspace_id column")
        except sqlite3.OperationalError:
            pass

    def learn_scoped(
        self,
        conn: sqlite3.Connection,
        node_id: int,
        content: str,
        metadata: dict[str, Any],
        layer: str = "episodic",
        namespace: str = "shared",
        scope: str = "",
        tag: str = "decision",
        importance: float = 1.0,
        symbol: str | None = None,
        structural_hash: str | None = None,
        branch: str = "main",
    ) -> int:
        """Insert observation with workspace_id scoping."""
        m_score = self._compute_materialized_score(importance, 0)
        meta_json = json.dumps(metadata)

        cur = conn.execute(
            """
            INSERT INTO observations (
                node_id, content, importance, layer, metadata, namespace, scope, tag,
                materialized_score, is_active, workspace_id, symbol, structural_hash, branch
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                content,
                importance,
                layer,
                meta_json,
                namespace,
                scope,
                tag,
                m_score,
                1,
                self.workspace_id.id,
                symbol,
                structural_hash,
                branch,
            ),
        )
        return cur.lastrowid or 0

    def _compute_materialized_score(self, importance: float, access_count: int) -> float:
        import math

        freq_factor = math.log10(access_count + 2)
        recency_factor = 1.0
        return importance * freq_factor * recency_factor
