import json
import logging
import sqlite3
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from kit.core.kit_invariants import enforce_no_global_contamination, sanitize_global_metadata
from kit.core.schema_factory import enable_wal, init_db

logger = logging.getLogger("kit.core")


class FactTag(StrEnum):
    INVARIANT = "invariant"
    DECISION = "decision"
    PREFERENCE = "preference"
    NOTE = "note"
    FRICTION = "friction"


class SAMBrainError(Exception):
    """Domain exception for the Cognitive Core."""

    pass


@dataclass(frozen=True, slots=True)
class Memory:
    """Immutable representation of a retrieved memory fact (v3.14 compliant)."""

    id: int
    node_uid: str
    content: str
    score: float
    brain_source: str
    layer: str = "episodic"
    namespace: str = "shared"
    scope: str = ""
    created_at: str = ""
    importance: float = 1.0
    symbol: str | None = None
    branch: str = "main"
    tag: str = "decision"
    is_active: bool = True
    supersedes_id: int | None = None
    materialized_score: float = 1.0


@dataclass(frozen=True, slots=True)
class RankingAssessment:
    """Confidence and ambiguity metadata for a ranked memory slice."""

    memories: list[Memory]
    confidence: float
    status: str


class SAMBrain:
    """
    Elite Cognitive Quad-Store AI Kernel (.kit).
    Hybrid Brain support (Local + Global) with Temporal Graph logic.
    """

    SQLITE_TIMEOUT_SECONDS = 1.0  # Fail-fast v1.2.2
    SQLITE_MAX_RETRIES = 3
    SQLITE_RETRY_BASE_DELAY_SECONDS = 0.1
    TAG_PRIORITY = {"invariant": 3, "decision": 2, "preference": 1, "note": 0, "friction": 0}
    AMBIGUITY_THRESHOLD = 0.2
    HIGH_CONFIDENCE_THRESHOLD = 0.5

    # ECL v1: Kernel Context
    active_frame: Optional[Any] = None # Will hold ExecutionFrame from kernel_fsm

    def __init__(self, db_path: Path, root_path: Path | None = None) -> None:
        self.db_path = db_path
        self.root_path = root_path or self._resolve_root(db_path.parent)
        self.global_db_path: Path | None = None
        self.current_branch = "main"
        self.cognition_version = 0
        self._init_db()
        self._refresh_version()

    def _refresh_version(self) -> None:
        """Fetch current cognition version from DB."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT version FROM branches WHERE name = ?", (self.current_branch,)).fetchone()
            if row:
                self.cognition_version = row["version"]

    def _increment_version(self, conn: sqlite3.Connection) -> None:
        """Atomic increment of branch version."""
        conn.execute("UPDATE branches SET version = version + 1 WHERE name = ?", (self.current_branch,))
        self.cognition_version += 1

    def _resolve_root(self, start_path: Path) -> Path:
        """Walk up to find the nearest .kit marker inside the nearest .git boundary."""
        curr = start_path.resolve()

        # 🔥 Step 1: Find Repo Boundary (.git)
        repo_root = None
        for parent in [curr] + list(curr.parents):
            if (parent / ".git").exists():
                repo_root = parent
                break

        # 🔥 Step 2: Walk but STOP at repo boundary
        for parent in [curr] + list(curr.parents):
            if (parent / ".kit").exists():
                return parent

            if repo_root and parent == repo_root:
                break

        # Không tìm thấy .kit trong boundary? KHÔNG FALLBACK! Cưỡng chế tạo mới tại start_path
        kit_dir = curr / ".kit"
        kit_dir.mkdir(parents=True, exist_ok=True)

        # EXPLICIT SIGNAL: observable mutation
        print(f"[kit] Initialized isolated brain at {curr}")
        return curr

    def get_normalized_scope(self, path: Path | str | None = None) -> str:
        """Convert path to a canonical scope string relative to root."""
        p = Path(path).resolve() if path else Path.cwd().resolve()
        try:
            rel = p.relative_to(self.root_path)
            return str(rel).replace("\\", "/") if str(rel) != "." else ""
        except ValueError:
            return ""  # Outside root

    def _get_connection(self, db_path: Path | None = None) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(
                str(db_path or self.db_path),
                check_same_thread=False,
                isolation_level=None,
                timeout=self.SQLITE_TIMEOUT_SECONDS,
            )
            conn.row_factory = sqlite3.Row
            enable_wal(conn)
            return conn
        except sqlite3.Error as e:
            raise SAMBrainError(f"Database connection failed: {e}") from e

    def get_connection(self, db_path: Path | None = None) -> sqlite3.Connection:
        """Public alias for _get_connection to allow external access."""
        return self._get_connection(db_path)

    @staticmethod
    def _is_retryable_sqlite_error(error: sqlite3.Error) -> bool:
        message = str(error).lower()
        return "database is locked" in message or "database table is locked" in message or "database is busy" in message

    def _run_write_transaction(self, operation: Any, db_path: Path | None = None) -> Any:
        target_db_path = db_path or self.db_path
        last_error: sqlite3.Error | None = None

        for attempt in range(self.SQLITE_MAX_RETRIES):
            conn = self._get_connection(target_db_path)
            try:
                conn.execute("BEGIN IMMEDIATE")
                result = operation(conn)
                conn.commit()
                return result
            except sqlite3.Error as error:
                conn.rollback()
                last_error = error
                if self._is_retryable_sqlite_error(error) and attempt < (self.SQLITE_MAX_RETRIES - 1):
                    time.sleep(self.SQLITE_RETRY_BASE_DELAY_SECONDS * (2**attempt))
                    continue
                raise
            finally:
                conn.close()

        assert last_error is not None
        raise last_error

    def attach_global(self, global_db_path: Path) -> None:
        """Attach the global brain for unified queries."""
        self.global_db_path = global_db_path
        with self._get_connection(global_db_path) as gconn:
            init_db(gconn)
        from kit.core.memory_router import MemoryRouter

        self._router = MemoryRouter(self.root_path, self.db_path, global_db_path)

    def get_workspace_id(self) -> str:
        """Return current workspace identity."""
        if hasattr(self, "_router"):
            return self._router.workspace_id.id
        from kit.core.memory_router import WorkspaceId

        ws = WorkspaceId.compute(self.root_path)
        return ws.id

    def _compute_materialized_score(self, importance: float, access_count: int, created_at: str | None = None) -> float:
        """
        Implementation of AMSB Core Scoring:
        Score = Importance * log10(AccessCount + 2) * (1 / sqrt(DaysOld + 1))
        """
        import math
        from datetime import datetime

        # log10 factor
        freq_factor = math.log10(access_count + 2)

        # Recency factor (DaysOld)
        if created_at:
            try:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                days_old = (datetime.now() - created_dt).days
                if days_old < 0:
                    days_old = 0
            except ValueError:
                days_old = 0
        else:
            days_old = 0

        recency_factor = 1.0 / math.sqrt(days_old + 1)

        return importance * freq_factor * recency_factor

    def _tag_bonus(self, tag: str) -> float:
        return {"invariant": 0.3, "decision": 0.2, "preference": 0.1, "note": 0.0, "friction": 0.0}.get(tag, 0.0)

    def _namespace_factor(self, namespace: str, agent_id: str | None) -> float:
        if agent_id and namespace == agent_id:
            return 1.2
        if namespace in {"shared", "project"}:
            return 1.0
        return 0.9

    def _namespace_bonus(self, namespace: str, agent_id: str | None) -> float:
        if agent_id and namespace == agent_id:
            return 0.1
        return 0.0

    @staticmethod
    def _fts_literal(term: str) -> str:
        """
        Escape a raw string as an FTS5 phrase literal.

        This prevents characters such as spaces, hyphens, or slashes from being
        interpreted as FTS operators when the caller intends a literal match.
        """
        return f'"{term.replace(chr(34), chr(34) * 2)}"'

    @staticmethod
    def _sqlite_string_literal(value: str) -> str:
        """Escape a Python string for safe interpolation into SQLite string literals."""
        return value.replace("'", "''")

    def _scope_bonus(
        self, memory_scope: str, current_scope: str, memory_symbol: str | None, symbol: str | None
    ) -> float:
        if symbol and memory_symbol == symbol:
            return 0.3
        if current_scope and memory_scope == current_scope:
            return 0.2
        if current_scope and memory_scope and current_scope.startswith(memory_scope):
            return 0.15
        if memory_scope in {"", "global"}:
            return 0.1
        return 0.0

    def calculate_runtime_score(
        self,
        memory: Memory,
        current_scope: str = "",
        symbol: str | None = None,
        agent_id: str | None = None,
        source_priority: float = 1.0,
    ) -> float:
        base = memory.materialized_score * source_priority * self._namespace_factor(memory.namespace, agent_id)
        return (
            base
            + self._tag_bonus(memory.tag)
            + self._namespace_bonus(memory.namespace, agent_id)
            + self._scope_bonus(
                memory.scope,
                current_scope,
                memory.symbol,
                symbol,
            )
        )

    def calculate_confidence(self, memories: list[Memory]) -> float:
        if not memories:
            return 0.0
        if len(memories) == 1:
            return 1.0
        top_score = memories[0].score
        runner_up_score = memories[1].score
        return max(0.0, (top_score - runner_up_score) / (abs(top_score) + 1e-6))

    def assess_ranked_memories(self, memories: list[Memory]) -> RankingAssessment:
        confidence = self.calculate_confidence(memories)
        if not memories:
            status = "EMPTY"
        elif confidence < self.AMBIGUITY_THRESHOLD:
            status = "AMBIGUOUS"
        elif confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            status = "HIGH_CONFIDENCE"
        else:
            status = "WEAK_SIGNAL"
        return RankingAssessment(memories=memories, confidence=confidence, status=status)

    def stream_events(self, poll_interval: float = 0.2):
        """Yields semantic events when the cognitive version increments."""
        import time
        from datetime import datetime

        last_version = self.cognition_version

        while True:
            time.sleep(poll_interval)

            with self._get_connection() as conn:
                row = conn.execute("SELECT version FROM branches WHERE name = ?", (self.current_branch,)).fetchone()
                current_version = row["version"] if row else 0

                if current_version > last_version:
                    obs_row = conn.execute(
                        "SELECT o.agent_id, n.uid as entity FROM observations o JOIN nodes n ON o.node_id = n.id WHERE o.branch = ? ORDER BY o.id DESC LIMIT 1",
                        (self.current_branch,),
                    ).fetchone()

                    origin = obs_row["agent_id"] if obs_row and obs_row["agent_id"] else "system"
                    entity = obs_row["entity"] if obs_row else "unknown"

                    event = {
                        "type": "memory.updated",
                        "version": current_version,
                        "entity": entity,
                        "origin": origin,
                        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                    yield event
                    last_version = current_version

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            init_db(conn)

    def render_context(self) -> None:
        """Export distilled project memory to internal .kit/context for AI Agents."""
        try:
            with self._get_connection() as conn:
                # Distill top 30 facts (Semantic layer + Specific Arch Markers)
                sql = """
                SELECT n.uid, o.content, o.scope, o.layer, o.importance, o.symbol
                FROM observations o
                JOIN nodes n ON o.node_id = n.id
                WHERE (o.layer = 'semantic' OR o.importance >= 0.7 OR o.content LIKE 'ARCH:%' OR o.content LIKE 'FIXME:%')
                   AND o.superseded_at IS NULL
                   AND o.branch = ?
                ORDER BY 
                   CASE WHEN o.content LIKE 'ARCH:%' THEN 1 ELSE 2 END,
                   o.importance DESC, 
                   o.created_at DESC
                LIMIT 30
                """
                rows = conn.execute(sql, (self.current_branch,)).fetchall()

                # 1. .kit/context (The internal AI manifest)
                kit_dir = self.root_path / ".kit"
                kit_dir.mkdir(parents=True, exist_ok=True)

                context_file = kit_dir / "context"
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                ctx_lines: list[str] = []
                ctx_lines.append("# .kit Project Context\n")
                ctx_lines.append(f"# Generated: {timestamp} | Root: {self.root_path.name}\n")
                ctx_lines.append(f"# Cognition-Version: {self.cognition_version}\n\n")
                for r in rows:
                    scope_prefix = f"[{r['scope']}] " if r["scope"] else ""
                    ctx_lines.append(f"- {scope_prefix}{r['content']}\n")

                new_ctx_content = "".join(ctx_lines)

                # Lazy write optimization to prevent IDE lag
                should_write_ctx = True
                if context_file.exists():
                    try:
                        with open(context_file, encoding="utf-8") as f:
                            old_ctx = f.read()
                            old_body = "\n".join(old_ctx.split("\n")[3:])
                            new_body = "\n".join(new_ctx_content.split("\n")[3:])
                            if old_body == new_body:
                                should_write_ctx = False
                    except (json.JSONDecodeError, OSError):
                        pass

                if should_write_ctx:
                    with open(context_file, "w", encoding="utf-8") as f:
                        f.write(new_ctx_content)

                # AGENTS.md AUTO-INJECT REMOVED [ARCHITECTURAL MANDATE v1.2.3 FIX]
                # We no longer modify AGENTS.md automatically to prevent Scope Bleed.

        except Exception as e:
            logger.exception("Failed to render context manifests")
            raise SAMBrainError("Failed to render context manifests") from e

    def learn(
        self,
        uid: str,
        content: str,
        kind: str = "observation",
        importance: float = 1.0,
        layer: str = "episodic",
        metadata: dict[str, Any] | None = None,
        to_global: bool = False,
        supersede_id: int | None = None,
        namespace: str = "shared",
        scope: str | None = None,
        agent_id: str | None = None,
        symbol: str | None = None,
        structural_hash: str | None = None,
        tag: str = FactTag.DECISION.value,
        skip_render: bool = False,
    ) -> int:
        """Learn a new observation at a specific node with STRICT Invariant Enforcement."""
        target_db = self.global_db_path if (to_global and self.global_db_path) else self.db_path

        # --- BƯỚC 1: XỬ LÝ DỮ LIỆU ĐẦU VÀO ---
        if to_global:
            normalized_scope = "GLOBAL"
            # Tẩy rửa Metadata: Tuyệt đối cấm các key rác của Local
            clean_metadata = sanitize_global_metadata(metadata or {})
        else:
            normalized_scope = scope if scope is not None else self.get_normalized_scope()
            clean_metadata = (metadata or {}).copy()

        # ECL v1: Authorize and Inject Frame Traceability
        from kit.core.kernel_fsm import StateMutationContract
        frame_id = StateMutationContract.authorize_mutation(self.active_frame)
        clean_metadata["_kernel_frame"] = frame_id
        if self.active_frame and hasattr(self.active_frame, "session_id"):
             clean_metadata["_kernel_session"] = self.active_frame.session_id

        # 🔥 CHUẨN HÓA TAG TRƯỚC KHI VÀO LÒ LUYỆN (Zero-Trust Boundary)
        normalized_tag = str(tag).strip().lower()

        # 🔥 VALIDATION (Phòng ngừa Agent / User truyền bậy)
        VALID_TAGS = {"invariant", "decision", "preference", "note", "legacy", "friction"}
        if normalized_tag not in VALID_TAGS:
            raise ValueError(f"[POLICY ENGINE] REJECTED: Invalid tag '{normalized_tag}'. Must be one of {VALID_TAGS}")

        # --- BƯỚC 2: CƯỠNG CHẾ BẤT BIẾN (INVARIANT ENFORCEMENT) ---
        # Đóng gói tạm dữ liệu để Thẩm phán kiểm duyệt
        test_entry = {"content": content, "scope": normalized_scope, "tag": normalized_tag, "metadata": clean_metadata}
        if to_global:
            enforce_no_global_contamination(test_entry)

        try:

            def _operation(conn: sqlite3.Connection) -> int:
                # 0. Handle Supersede (Atomic Transaction)
                if supersede_id:
                    conn.execute(
                        "UPDATE observations SET superseded_at = CURRENT_TIMESTAMP, is_active = 0 WHERE id = ?",
                        (supersede_id,),
                    )

                # 1. Upsert Node
                target_uid = (uid or "fact").lower()
                conn.execute(
                    "INSERT INTO nodes (uid, kind) VALUES (?, ?) ON CONFLICT(uid) DO UPDATE SET uid=uid",
                    (target_uid, kind),
                )
                node_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", (target_uid,)).fetchone()
                node_id = node_row["id"]

                # 2. Get head commit of current branch
                head_row = conn.execute(
                    "SELECT head_commit_id FROM branches WHERE name = ?", (self.current_branch,)
                ).fetchone()
                commit_id = head_row["head_commit_id"] if head_row else "ROOT"

                # 3. Insert Observation (Dùng clean_metadata)
                meta_json = json.dumps(clean_metadata)
                m_score = self._compute_materialized_score(importance, 0)

                sql = """
                INSERT INTO observations (
                    node_id, content, importance, layer, metadata, namespace, scope, agent_id, 
                    commit_id, branch, symbol, structural_hash, materialized_score, tag, is_active, supersedes_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                cur = conn.execute(
                    sql,
                    (
                        node_id,
                        content,
                        importance,
                        layer,
                        meta_json,
                        namespace,
                        normalized_scope,
                        agent_id,
                        commit_id,
                        self.current_branch,
                        symbol,
                        structural_hash,
                        m_score,
                        normalized_tag,
                        1,
                        supersede_id,
                    ),
                )
                fact_id = cur.lastrowid
                if fact_id is None:
                    raise SAMBrainError("Failed to insert observation: lastrowid is None")

                self._increment_version(conn)
                return fact_id

            fact_id = self._run_write_transaction(_operation, target_db)
            # Render context removed from automatic cycle [v1.2.3 HOTFIX]
            # Use 'kit render' manually to update manifests.
            return fact_id
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to learn observation: {e}") from e

    def link(
        self,
        src_uid: str,
        dst_uid: str,
        rel: str,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a directed edge between two nodes."""
        try:

            def _operation(conn: sqlite3.Connection) -> None:
                src_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", (src_uid.lower(),)).fetchone()
                dst_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", (dst_uid.lower(),)).fetchone()

                if not src_row or not dst_row:
                    raise SAMBrainError(f"Node not found: {src_uid if not src_row else dst_uid}")

                meta_json = json.dumps(metadata or {"weight": weight})
                conn.execute(
                    "INSERT INTO edges (subject_id, predicate, object_id, metadata) VALUES (?, ?, ?, ?)",
                    (src_row["id"], rel, dst_row["id"], meta_json),
                )
                return None

            self._run_write_transaction(_operation)
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to link nodes: {e}") from e

    def search(
        self,
        query: str,
        limit: int = 15,
        at_timestamp: str | None = None,
        agent_id: str | None = None,
        fast: bool = False,
    ) -> list[Memory]:
        """Hybrid FTS Search across both brains (Namespace-aware)."""
        results: list[Memory] = []
        candidate_limit = max(limit * 5, limit)

        def run_query(
            conn: sqlite3.Connection, prefix: str = "", priority: float = 1.0, source: str = "project"
        ) -> None:
            p = f"{prefix}." if prefix else ""
            sql = f"""
            SELECT o.*, n.uid as node_uid
            FROM {p}observations o
            JOIN {p}nodes n ON o.node_id = n.id
            WHERE o.id IN (SELECT rowid FROM {p}observations_fts WHERE {p}observations_fts MATCH ?)
              AND (o.branch = ?)
              AND o.is_active = 1
            ORDER BY 
                o.materialized_score DESC,
                o.created_at DESC
            LIMIT ?
            """
            cur = conn.execute(sql, (self._fts_literal(query), self.current_branch, candidate_limit))
            for row in cur.fetchall():
                memory = Memory(
                    id=row["id"],
                    node_uid=row["node_uid"],
                    content=row["content"],
                    score=0.0,
                    brain_source=source,
                    layer=row["layer"],
                    namespace=row["namespace"],
                    branch=row["branch"],
                    created_at=row["created_at"],
                    importance=row["importance"],
                    symbol=row["symbol"],
                    tag=row["tag"],
                    scope=row["scope"],
                    is_active=bool(row["is_active"]),
                    supersedes_id=row["supersedes_id"],
                    materialized_score=row["materialized_score"],
                )
                results.append(
                    replace(
                        memory,
                        score=self.calculate_runtime_score(memory, agent_id=agent_id, source_priority=priority),
                    )
                )

        # 1. Project Brain
        with self._get_connection() as conn:
            run_query(conn, priority=1.5, source="project")

        # 2. Global Brain
        if self.global_db_path:
            with self._get_connection(self.global_db_path) as gconn:
                run_query(gconn, priority=1.0, source="global")

        # Sort combined results: Tag Priority first, then Score
        results.sort(key=lambda x: (self.TAG_PRIORITY.get(x.tag, 0), x.score, x.created_at), reverse=True)
        return results[:limit]

    def recall(
        self,
        entities: list[str],
        limit: int = 15,
        at: str | None = None,
        agent_id: str | None = None,
        here: bool = False,
        symbol: str | None = None,
        query: str | None = None,
        with_global: bool = False,
        fast: bool = False,
        include_profile: bool = False,
    ) -> tuple[list[Memory], dict[str, float] | None]:
        """Ranked recall with support for symbol anchoring and stage profiling."""
        import time
        from kit.core.kit_cognitive_core import Memory

        profile = {"sql": 0.0, "ranking": 0.0, "hydration": 0.0, "total": 0.0} if include_profile else None
        start_total = time.perf_counter()
        memories: list[Memory] = []
        candidate_limit = max(limit * 5, limit)

        # Internal helper for querying a single brain
        def _recall_from(
            conn: sqlite3.Connection, prefix: str = "", priority: float = 1.5, source: str = "project"
        ) -> None:
            p = f"{prefix}." if prefix else ""
            current_scope = self.get_normalized_scope() if here else ""

            # ... (Existing logic for where clauses)
            symbol_where_clause = "OR o.symbol = ?" if symbol else ""
            scope_filter_clause = ""
            scopes = []
            if here:
                parts = current_scope.split("/") if current_scope else []
                scopes = ["/".join(parts[:i]) for i in range(len(parts) + 1)]
                scope_placeholders = ",".join(["?"] * len(scopes))
                scope_filter_clause = f"(o.scope IN ({scope_placeholders}) OR o.scope = '')"

            query_filter_clause = ""
            if query:
                query_filter_clause = (
                    f"o.id IN (SELECT rowid FROM {p}observations_fts WHERE {p}observations_fts MATCH ?)"
                )

            entity_filter_clause = ""
            if entities:
                placeholders = ",".join(["?"] * len(entities))
                uid_clause = f"n.uid IN ({placeholders})"
                if not query:
                    entity_filter_clause = f"({uid_clause} OR o.id IN (SELECT rowid FROM {p}observations_fts WHERE {p}observations_fts MATCH ?))"
                else:
                    entity_filter_clause = uid_clause

            where_clauses: list[str] = []
            if entity_filter_clause: where_clauses.append(entity_filter_clause)
            if scope_filter_clause: where_clauses.append(scope_filter_clause)
            if query_filter_clause: where_clauses.append(query_filter_clause)
            if symbol_where_clause: where_clauses.append(f"(1=0 {symbol_where_clause})")
            final_where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

            sql = f"""
            SELECT o.*, n.uid as node_uid
            FROM {p}observations o
            JOIN {p}nodes n ON o.node_id = n.id
            WHERE {final_where_clause}
              AND (o.branch = ?)
              AND o.is_active = 1
            ORDER BY o.materialized_score DESC, o.created_at DESC
            LIMIT ?
            """
            where_params: list[str] = []
            if entities:
                where_params.extend([e.lower() for e in entities])
                if not query: where_params.append(" OR ".join(self._fts_literal(e) for e in entities))
            if here: where_params.extend(scopes)
            if query: where_params.append(query)
            if symbol: where_params.append(symbol)
            all_params: list[Any] = where_params + [self.current_branch, candidate_limit]

            # !!! STAGE 1: SQL EXECTION
            s_sql = time.perf_counter()
            cur = conn.execute(sql, all_params)
            rows = cur.fetchall()
            if profile is not None: profile["sql"] += (time.perf_counter() - s_sql)

            # !!! STAGE 2: HYDRATION & INITIAL RANKING
            for row in rows:
                s_hyd = time.perf_counter()
                memory = Memory(
                    id=row["id"],
                    node_uid=row["node_uid"],
                    content=row["content"],
                    score=0.0,
                    brain_source=source,
                    layer=row["layer"],
                    namespace=row["namespace"],
                    branch=row["branch"],
                    created_at=row["created_at"],
                    importance=row["importance"],
                    symbol=row["symbol"],
                    tag=row["tag"],
                    scope=row["scope"],
                    is_active=bool(row["is_active"]),
                    supersedes_id=row["supersedes_id"],
                    materialized_score=row["materialized_score"],
                )
                if profile is not None: profile["hydration"] += (time.perf_counter() - s_hyd)

                s_rank = time.perf_counter()
                scored_memory = replace(
                    memory,
                    score=self.calculate_runtime_score(
                        memory,
                        current_scope=current_scope,
                        symbol=symbol,
                        agent_id=agent_id,
                        source_priority=priority,
                    ),
                )
                if profile is not None: profile["ranking"] += (time.perf_counter() - s_rank)
                memories.append(scored_memory)

        with self._get_connection() as conn:
            _recall_from(conn, priority=1.5, source="project")

        if with_global and self.global_db_path:
            try:
                if self.global_db_path.exists():
                    with self._get_connection(self.global_db_path) as gconn:
                        _recall_from(gconn, prefix="", priority=1.0, source="global")
            except sqlite3.Error as e:
                logger.warning(f"Global Brain recall failed: {e}")

        # !!! STAGE 3: FINAL SORTING
        s_sort = time.perf_counter()
        memories.sort(key=lambda x: (self.TAG_PRIORITY.get(x.tag, 0), x.score, x.created_at), reverse=True)
        final_memories = memories[:limit]
        if profile is not None: profile["ranking"] += (time.perf_counter() - s_sort)

        if profile is not None: 
            profile["total"] = time.perf_counter() - start_total

        return final_memories, profile

    def recall_with_assessment(
        self,
        entities: list[str],
        limit: int = 15,
        at: str | None = None,
        agent_id: str | None = None,
        here: bool = False,
        symbol: str | None = None,
        with_global: bool = False,
        fast: bool = False,
    ) -> RankingAssessment:
        memories = self.recall(
            entities,
            limit=limit,
            at=at,
            agent_id=agent_id,
            here=here,
            symbol=symbol,
            with_global=with_global,
            fast=fast,
        )
        return self.assess_ranked_memories(memories)

    def get_stats(self) -> dict[str, Any]:
        """Retrieve dual-brain metrics."""
        stats: dict[str, dict[str, int]] = {"project": {}, "global": {}}

        def get_db_stats(conn: sqlite3.Connection, prefix: str = "") -> dict[str, int]:
            p = f"{prefix}." if prefix else ""
            return {
                "nodes": conn.execute(f"SELECT COUNT(*) FROM {p}nodes").fetchone()[0],
                "edges": conn.execute(f"SELECT COUNT(*) FROM {p}edges").fetchone()[0],
                "observations": conn.execute(f"SELECT COUNT(*) FROM {p}observations").fetchone()[0],
                "baked": conn.execute(f"SELECT COUNT(*) FROM {p}observations WHERE is_baked = 1").fetchone()[0],
                "skills": conn.execute(f"SELECT COUNT(*) FROM {p}nodes WHERE kind = 'skill'").fetchone()[0],
            }

        with self._get_connection() as conn:
            stats["project"] = get_db_stats(conn)
            if self.global_db_path:
                escaped_path = self._sqlite_string_literal(str(self.global_db_path))
                conn.execute(f"ATTACH DATABASE '{escaped_path}' AS g")
                stats["global"] = get_db_stats(conn, "g")
        return stats

    def lookup_hash(self, symbol: str) -> str | None:
        """
        Retrieve the latest active structural hash for a given symbol identity (UUID).
        Implementation of Phase B Drift Detection (v1.2.4).
        """
        if not symbol:
            return None

        with self._get_connection() as conn:
            # We look for the most recent active observation anchored to this symbol
            sql = """
            SELECT structural_hash 
            FROM observations 
            WHERE symbol = ? AND is_active = 1 
            ORDER BY created_at DESC 
            LIMIT 1
            """
            row = conn.execute(sql, (symbol,)).fetchone()
            return row["structural_hash"] if row else None

    def touch_fact(self, fact_id: int) -> None:
        """Increment access count and refresh recency (v3.14 compliant)."""
        try:

            def _operation(conn: sqlite3.Connection) -> None:
                conn.execute(
                    """UPDATE observations 
                       SET access_count = access_count + 1, 
                           last_accessed_at = CURRENT_TIMESTAMP,
                           materialized_score = importance * ((access_count + 2) / (access_count + 6.0)) * 
                               CASE layer WHEN 'working' THEN 3.0 WHEN 'episodic' THEN 2.0 WHEN 'semantic' THEN 1.5 ELSE 1.0 END
                       WHERE id = ?""",
                    (fact_id,),
                )
                return None

            self._run_write_transaction(_operation)
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to touch fact: {e}") from e

    def promote_memories(self, threshold: int = 5) -> int:
        """Promote Episodic facts to Semantic based on access frequency."""
        try:

            def _operation(conn: sqlite3.Connection) -> int:
                cur = conn.execute(
                    """UPDATE observations 
                       SET layer = 'semantic',
                           materialized_score = importance * ((access_count + 1) / (access_count + 5.0)) * 1.5
                       WHERE layer = 'episodic' AND access_count >= ?""",
                    (threshold,),
                )
                return cur.rowcount

            return self._run_write_transaction(_operation)
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to promote memories: {e}") from e

    def process_gc(self) -> None:
        """Memory lifecycle maintenance (WIP - Phase 3 focus)."""
        pass

    def checkout(self, branch_name: str, create: bool = False) -> None:
        """Switch to a specific memory branch."""
        try:

            def _operation(conn: sqlite3.Connection) -> None:
                row = conn.execute("SELECT name FROM branches WHERE name = ?", (branch_name,)).fetchone()
                if not row:
                    if create:
                        # Get current head
                        current_head = conn.execute(
                            "SELECT head_commit_id FROM branches WHERE name = ?", (self.current_branch,)
                        ).fetchone()
                        head_id = current_head["head_commit_id"] if current_head else "ROOT"
                        conn.execute(
                            "INSERT INTO branches (name, head_commit_id) VALUES (?, ?)", (branch_name, head_id)
                        )
                    else:
                        raise SAMBrainError(f"Branch '{branch_name}' not found.")

                self.current_branch = branch_name
                return None

            self._run_write_transaction(_operation)
            self._refresh_version()
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to switch branch: {e}") from e

    def commit(self, message: str, agent_id: str | None = None, skip_render: bool = False) -> str:
        """Freeze current memory state as a commit."""
        import hashlib
        import uuid

        commit_id = hashlib.sha1(str(uuid.uuid4()).encode()).hexdigest()[:8]

        try:

            def _operation(conn: sqlite3.Connection) -> str:
                cur_head = conn.execute(
                    "SELECT head_commit_id FROM branches WHERE name = ?", (self.current_branch,)
                ).fetchone()
                parent_id = cur_head["head_commit_id"] if cur_head else None

                conn.execute(
                    "INSERT INTO commits (id, parent_id, agent_id, message) VALUES (?, ?, ?, ?)",
                    (commit_id, parent_id, agent_id, message),
                )
                conn.execute("UPDATE branches SET head_commit_id = ? WHERE name = ?", (commit_id, self.current_branch))
                return commit_id

            committed_id = self._run_write_transaction(_operation)
            # Render context removed from automatic cycle [v1.2.3 HOTFIX]
            return committed_id
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to commit memory: {e}") from e

    def export_for_prompt(self, entities: list[str], limit: int = 3, budget: int = 200) -> str:
        """Compact memory export for LLM prompts."""
        bounded_limit = min(limit, 3)
        memories = self.recall(entities, bounded_limit)
        if not memories:
            return ""

        output = ["<kit_memory>"]
        used_chars = len(output[0]) + len("</kit_memory>") + 1
        for m in memories:
            line = f"[{m.brain_source}:{m.node_uid}] {m.content.splitlines()[0][:80]}"
            projected_chars = used_chars + len(line) + 1
            if projected_chars > budget:
                break
            output.append(line)
            used_chars = projected_chars

        if len(output) == 1:
            return ""

        output.append("</kit_memory>")
        return "\n".join(output)

    def get_blame(self, symbol: str) -> list[dict[str, Any]]:
        """Retrieve architectural history for a specific symbol."""
        with self._get_connection() as conn:
            sql = """
            SELECT o.id, o.content, o.agent_id, o.created_at, c.message as commit_msg
            FROM observations o
            LEFT JOIN commits c ON o.commit_id = c.id
            WHERE o.symbol = ?
            ORDER BY o.created_at DESC
            """
            return [dict(r) for r in conn.execute(sql, (symbol,)).fetchall()]

    def get_semantic_observations(
        self,
        branch: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get observations by branch and/or tags for governance checks."""
        branch = branch or self.current_branch
        with self._get_connection() as conn:
            sql = """
            SELECT tag, content FROM observations 
            WHERE branch = ? AND (layer = 'semantic' OR tag IN (?, ?, ?))
            ORDER BY materialized_score DESC LIMIT ?
            """
            default_tags = ("invariant", "decision", "preference")
            tag_params = tags or list(default_tags)
            while len(tag_params) < 3:
                tag_params.append("note")
            params = (branch, tag_params[0], tag_params[1], tag_params[2], limit)
            try:
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
            except sqlite3.OperationalError:
                sql_fallback = """
                SELECT 'decision' as tag, content FROM observations 
                WHERE branch = ? AND layer = 'semantic'
                ORDER BY materialized_score DESC LIMIT ?
                """
                return [dict(r) for r in conn.execute(sql_fallback, (branch, limit)).fetchall()]
