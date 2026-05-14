"""Kit Memory Commit Kernel (Stage 5.5.2).

Ensures deterministic memory writes and snapshot consistency.
Acts as an Epistemic Firewall between Ingestion (IO) and Cognition (Recall).
"""

from __future__ import annotations
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Set

if TYPE_CHECKING:
    from kit.core.kit_cognitive_core import SAMBrain

logger = logging.getLogger("kit.commit_kernel")

@dataclass
class CommitEvent:
    content: str
    symbol: str
    metadata: Dict
    structural_hash: str
    timestamp: float = field(default_factory=time.time)

class CommitQueue:
    """Deterministic Commit Layer with Snapshot Consistency."""
    
    def __init__(self, brain: SAMBrain, clock_seconds: float = 5.0, batch_limit: int = 100, on_flush: Optional[Callable[[List[CommitEvent]], None]] = None):
        self.brain = brain
        self.clock_seconds = clock_seconds
        self.batch_limit = batch_limit
        self.on_flush = on_flush
        
        self._queue: List[CommitEvent] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # v1.2.5-TITANIUM: Dedicated Commit Thread (The Clock)
        self._clock_thread: Optional[threading.Thread] = None
        
    def start(self):
        """Start the background commit clock."""
        if self._clock_thread and self._clock_thread.is_alive():
            return
            
        self._stop_event.clear()
        self._clock_thread = threading.Thread(target=self._run_clock, name="Kit-Commit-Clock", daemon=True)
        self._clock_thread.start()
        logger.info(f"CommitKernel: Clock started (interval: {self.clock_seconds}s)")

    def add(self, event: CommitEvent):
        """Append-only push to the commit queue."""
        with self._lock:
            self._queue.append(event)
            # v1.2.5: Immediate flush if batch limit reached to prevent memory bloat
            if len(self._queue) >= self.batch_limit:
                logger.debug("CommitKernel: Batch limit reached. Triggering early flush.")
                self.flush()

    def flush(self):
        """Perform atomic batch commit to SQLite."""
        with self._lock:
            if not self._queue:
                return
            
            count = len(self._queue)
            logger.info(f"CommitKernel: Committing batch of {count} events...")
            
            try:
                def _batch_commit_op(conn: sqlite3.Connection):
                    for event in self._queue:
                        # PURE IO: No triggers, no SRE, no repair during this phase.
                        # We just commit the raw structural perception.
                        
                        # node upsert
                        node_uid = f"sensor:{event.structural_hash}"
                        conn.execute("""
                            INSERT INTO nodes (uid, node_type, status, visibility)
                            VALUES (?, 'observation', 'active', 'local')
                            ON CONFLICT(uid) DO NOTHING
                        """, (node_uid,))
                        
                        node_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", (node_uid,)).fetchone()
                        node_id = node_row["id"]
                        
                        # observation insert
                        conn.execute("""
                            INSERT INTO observations 
                            (node_id, content, symbol, symbol_source, importance, materialized_score, metadata, structural_hash, tag, layer)
                            VALUES (?, ?, ?, 'sensor', 0.1, 0.1, ?, ?, 'pattern', 'semantic')
                        """, (
                            node_id, 
                            event.content, 
                            event.symbol, 
                            json.dumps(event.metadata), 
                            event.structural_hash
                        ))
                
                # Perform the transaction
                self.brain._run_write_transaction(_batch_commit_op)
                
                # v1.2.5-STAGE5.5.3: Graduation Callback
                committed_events = list(self._queue)
                self._queue.clear()
                
                if self.on_flush:
                    try:
                        self.on_flush(committed_events)
                    except Exception as e:
                        logger.error(f"CommitKernel: Graduation callback failed: {e}")

                logger.info(f"CommitKernel: Successfully committed {count} events. Snapshot synchronized.")
                
            except Exception as e:
                # v1.2.5-TITANIUM: On failure, we KEEP the queue for next retry
                # This ensures zero-data-loss for structural streams.
                logger.error(f"CommitKernel: Batch commit failed: {e}. Queue preserved for retry.")

    def _run_clock(self):
        """Internal loop for the deterministic commit clock."""
        while not self._stop_event.is_set():
            time.sleep(self.clock_seconds)
            logger.debug("CommitKernel: Clock tick.")
            if self._queue:
                self.flush()

    def shutdown(self):
        """Graceful shutdown: stop clock and perform final flush."""
        logger.info("CommitKernel: Shutting down...")
        self._stop_event.set()
        if self._clock_thread:
            self._clock_thread.join(timeout=2.0)
        self.flush()
        logger.info("CommitKernel: Shutdown complete.")
