import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("kit.storage")


@dataclass
class StorageConfig:
    """Storage configuration for production-grade persistence."""

    wal_mode: bool = True
    synchronous: str = "NORMAL"
    busy_timeout_ms: int = 5000
    max_retries: int = 3
    retry_base_delay_ms: int = 100
    enable_memory_fallback: bool = True
    memory_buffer_size: int = 100


class StorageError(Exception):
    """Storage layer exception."""

    pass


class StorageLockError(StorageError):
    """File lock acquisition failed."""

    pass


class StorageCommitError(StorageError):
    """Transaction commit failed."""

    pass


class InMemoryBuffer:
    """In-memory fallback when file is locked."""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._buffer: list[dict[str, Any]] = []

    def add(self, operation: dict[str, Any]) -> bool:
        if len(self._buffer) >= self.max_size:
            self._buffer.pop(0)
        self._buffer.append(operation)
        return True

    def flush(self) -> list[dict[str, Any]]:
        ops = self._buffer.copy()
        self._buffer.clear()
        return ops

    def __len__(self) -> int:
        return len(self._buffer)

    def is_empty(self) -> bool:
        return len(self._buffer) == 0


@dataclass
class StorageAdapter:
    """
    Production-grade storage layer with WAL, retry, and in-memory fallback.

    Responsibilities:
    - Atomic commit
    - IDE file lock resilience (Antigravity-safe)
    - In-memory buffer when disk is unavailable
    - Transaction safety
    """

    db_path: Path
    config: StorageConfig = field(default_factory=StorageConfig)
    _memory_buffer: InMemoryBuffer = field(default_factory=lambda: InMemoryBuffer())
    _is_connected: bool = field(default=False, init=False)

    @staticmethod
    def for_workspace(db_path: Path) -> StorageAdapter:
        """Factory for workspace-scoped storage."""
        return StorageAdapter(db_path)

    def get_connection(self) -> sqlite3.Connection:
        """Get WAL-enabled connection with retry."""
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                conn = self._create_connection()
                self._is_connected = True
                return conn
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                last_error = e
                error_msg = str(e).lower()

                if "locked" in error_msg or "busy" in error_msg:
                    delay = self.config.retry_base_delay_ms * (2**attempt)
                    logger.warning(f"DB locked, retrying in {delay}ms (attempt {attempt + 1})")
                    time.sleep(delay / 1000)
                    continue

                raise StorageLockError(f"Cannot acquire DB: {e}") from e

        raise StorageLockError(f"Max retries exceeded: {last_error}") from last_error

    def _create_connection(self) -> sqlite3.Connection:
        """Create new DB connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,
            timeout=self.config.busy_timeout_ms / 1000,
        )
        conn.row_factory = sqlite3.Row

        if self.config.wal_mode:
            conn.execute("PRAGMA journal_mode=WAL")

        conn.execute(f"PRAGMA synchronous={self.config.synchronous}")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(f"PRAGMA busy_timeout={self.config.busy_timeout_ms}")

        return conn

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
        commit: bool = True,
    ) -> sqlite3.Cursor:
        """Execute SQL with automatic retry and fallback."""
        conn = self.get_connection()

        try:
            cursor = conn.execute(sql, params)

            if commit:
                conn.commit()

            return cursor

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            conn.rollback()
            error_msg = str(e).lower()

            if "locked" in error_msg or "busy" in error_msg:
                if self.config.enable_memory_fallback:
                    logger.warning(f"DB locked, buffering to memory: {e}")
                    return self._buffer_operation(sql, params)
                raise StorageLockError(f"DB locked and fallback disabled: {e}") from e

            raise StorageCommitError(f"Commit failed: {e}") from e

        finally:
            self._close_if_needed(conn)

    def executemany(
        self,
        sql: str,
        params: list[tuple[Any, ...]],
        commit: bool = True,
    ) -> sqlite3.Cursor:
        """Execute batch SQL with retry."""
        conn = self.get_connection()

        try:
            cursor = conn.executemany(sql, params)

            if commit:
                conn.commit()

            return cursor

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            conn.rollback()
            raise StorageCommitError(f"Batch commit failed: {e}") from e

        finally:
            self._close_if_needed(conn)

    def _buffer_operation(self, sql: str, params: tuple[Any, ...]) -> Any:
        """Buffer operation to memory when disk is unavailable."""
        self._memory_buffer.add(
            {
                "sql": sql,
                "params": params,
                "timestamp": time.time(),
            }
        )
        logger.info(f"Buffered to memory (buffer size: {len(self._memory_buffer)})")
        return None

    def _close_if_needed(self, conn: sqlite3.Connection) -> None:
        """Close connection if not needed for subsequent operations."""
        if not self._memory_buffer.is_empty():
            return

        try:
            conn.close()
            self._is_connected = False
        except Exception:
            pass

    def flush_buffer(self) -> int:
        """Flush memory buffer to disk. Returns count of flushed operations."""
        if self._memory_buffer.is_empty():
            return 0

        ops = self._memory_buffer.flush()
        flushed = 0

        conn = self.get_connection()

        try:
            conn.execute("BEGIN IMMEDIATE")

            for op in ops:
                try:
                    conn.execute(op["sql"], op["params"])
                    flushed += 1
                except Exception as e:
                    logger.error(f"Flush failed for op: {e}")

            conn.commit()
            logger.info(f"Flushed {flushed} operations to disk")

        except Exception as e:
            conn.rollback()
            logger.error(f"Flush transaction failed: {e}")

        finally:
            self._close_if_needed(conn)

        return flushed

    def read(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        """Read with retry."""
        conn = self.get_connection()

        try:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

        finally:
            self._close_if_needed(conn)
