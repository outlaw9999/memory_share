"""
kit_baking.py — KIT v1.2.4-LOCK: Structural Graduation Engine.

The ONLY place where Vantage is called for user-submitted content.
Triggered explicitly by: `kit bake` or as the first step of `kit reflect`.

State machine:
  is_baked=0 (Raw Perception)  --> run_baking_pass() --> is_baked=1 (Verified Truth)
                                                     \\-> is_baked=-1 (Toxic: unanalyzable)
"""
import logging
import threading
from typing import Any

from kit.core.kit_cognitive_core import SAMBrain

logger = logging.getLogger("kit.baking")


def run_baking_pass(brain: SAMBrain, timeout: int = 10) -> dict:
    """
    Scan for unbaked observations and graduate them via Vantage structural analysis.
    This is the ONLY place Vantage is invoked for content submitted via `kit learn`.

    Returns a dict with counts: {total, baked, skipped, toxic}.
    """
    from kit.core.contract import normalize_vantage_signal
    from kit.core.kit_vantage import invoke_vantage_on_text

    stats = {"total": 0, "baked": 0, "skipped": 0, "toxic": 0}

    with brain._get_connection() as conn:
        rows = conn.execute(
            "SELECT id, content, symbol FROM observations WHERE is_baked = 0 ORDER BY created_at ASC",
        ).fetchall()

    stats["total"] = len(rows)
    if not rows:
        logger.info("[baking] No pending observations. Brain is fully baked.")
        return stats

    logger.info(f"[baking] Starting baking pass: {stats['total']} pending observations.")

    for row in rows:
        obs_id = row["id"]
        content = row["content"]
        symbol_hint = row["symbol"]

        signals = []
        try:
            # Only invoke Vantage if content looks like it could contain symbols
            if any(kw in content for kw in ("def ", "class ", "fn ", "func ", "import ")):
                signals = invoke_vantage_on_text(content, timeout=timeout, strict=False)
        except Exception as e:
            logger.warning(f"[baking] Vantage failed for obs_id={obs_id}: {e}. Marking as toxic.")
            _mark_observation(brain, obs_id, is_baked=-1)
            stats["toxic"] += 1
            continue

        if not signals:
            # No structural signals found — still valid, just not structural.
            # Bake it as-is (Perception → Verified Fact without structural hash).
            _mark_observation(brain, obs_id, is_baked=1)
            stats["baked"] += 1
            continue

        # Process the first signal (primary symbol). Additional signals in a multi-symbol
        # snippet will be handled by subsequent observations created per-symbol in future passes.
        primary_sig = signals[0]
        try:
            normalize_vantage_signal({
                "type": primary_sig.uid.split(":")[-1],
                "id": primary_sig.symbol,
                "normalized_hash": primary_sig.structural_hash,
                "uuid": primary_sig.evidence,
            })

            # Detect structural drift: if existing hash differs, create a SUPERSEDED_BY link
            existing_hash = brain.lookup_hash(primary_sig.symbol) if primary_sig.symbol else None

            if existing_hash and existing_hash != primary_sig.structural_hash:
                logger.info(
                    f"[baking] DRIFT:STRUCTURAL detected for symbol={primary_sig.symbol}. "
                    f"old_hash={existing_hash[:12]}... new_hash={(primary_sig.structural_hash or '')[:12]}..."
                )
                # Log drift as a Friction fact
                brain.learn(
                    uid=f"drift:{primary_sig.symbol or obs_id}:{obs_id}",
                    content=(
                        f"DRIFT:STRUCTURAL | symbol={primary_sig.symbol} | "
                        f"old_hash={existing_hash} | new_hash={primary_sig.structural_hash}"
                    ),
                    tag="friction",
                    kind="observation",
                    importance=0.8,
                    layer="episodic",
                )

            # Stamp the observation with structural truth
            _stamp_observation(
                brain, obs_id,
                symbol=primary_sig.symbol or symbol_hint,
                structural_hash=primary_sig.structural_hash,
            )
            stats["baked"] += 1

        except Exception as e:
            logger.warning(f"[baking] Normalization failed for obs_id={obs_id}: {e}. Marking as toxic.")
            _mark_observation(brain, obs_id, is_baked=-1)
            stats["toxic"] += 1

    logger.info(
        f"[baking] Pass complete. "
        f"baked={stats['baked']} skipped={stats['skipped']} toxic={stats['toxic']}"
    )
    return stats


# --- Async Bake Worker (v1.2.3-STABLE) ---
_BAKE_LOCK = threading.Lock()

def trigger_async_bake(brain: SAMBrain, timeout: int = 5) -> None:
    """
    Launch a background pass to graduate observations.
    Non-blocking: returns immediately.
    """
    def _worker():
        # Prevent multiple concurrent bake passes in the same process
        if not _BAKE_LOCK.acquire(blocking=False):
            return
        try:
            run_baking_pass(brain, timeout=timeout)
        finally:
            _BAKE_LOCK.release()

    import os
    if os.environ.get("KIT_DISABLE_ASYNC_BAKE") == "1":
        # Synchronous execution for tests/CLI integration
        run_baking_pass(brain, timeout=timeout)
        return

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def _mark_observation(brain: SAMBrain, obs_id: int, is_baked: int) -> None:
    """Mark an observation's bake state."""
    def _op(conn):
        conn.execute("UPDATE observations SET is_baked = ? WHERE id = ?", (is_baked, obs_id))
    brain._run_write_transaction(_op)


def _stamp_observation(
    brain: SAMBrain,
    obs_id: int,
    symbol: str | None,
    structural_hash: str | None,
) -> None:
    """Stamp an observation with structural truth and mark as baked."""
    def _op(conn):
        conn.execute(
            "UPDATE observations SET is_baked = 1, symbol = ?, structural_hash = ? WHERE id = ?",
            (symbol, structural_hash, obs_id),
        )
    brain._run_write_transaction(_op)
