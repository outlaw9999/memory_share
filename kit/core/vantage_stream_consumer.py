"""Vantage Stream Consumer (Stage 5.5.1).

Responsible for consuming structural event streams from Vantage.
Decouples perception (Vantage) from cognition (Kit).
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from kit.core.kit_cognitive_core import SAMBrain

logger = logging.getLogger("kit.vantage_consumer")


class VantageStreamConsumer:
    """Consumes JSONL events from .vantage/outstream.jsonl."""

    def __init__(self, brain: SAMBrain, stream_path: Path | None = None):
        self.brain = brain
        self.stream_path = stream_path or brain.root_path / ".vantage" / "outstream.jsonl"
        self._last_position = 0

    def consume_batch(self) -> int:
        """Process all pending events in the stream."""
        if not self.stream_path.exists():
            return 0

        count = 0
        try:
            with open(self.stream_path, encoding="utf-8") as f:
                # Seek to last known position to support incremental processing
                f.seek(self._last_position)

                events = []
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)

                        # --- [CONTRACT GUARD] Version Validation ---
                        # Standard v1.2.5 stream events should include a version field 'v'
                        if "v" in event and event["v"] != "1.2.5":
                            logger.warning(
                                f"Consumer: Version mismatch in stream event. Expected 1.2.5, got {event['v']}"
                            )
                            if os.getenv("KIT_STRICT_CONTRACT") == "1":
                                continue

                        events.append(event)
                        count += 1
                    except json.JSONDecodeError as e:
                        # --- [HARDENING] Corruption Resilience ---
                        logger.error(f"Consumer: CRITICAL - Corrupted JSONL line detected. Skipping. Error: {e}")
                        # Move to next line automatically by loop
                        continue

                if events:
                    self._ingest_events(events)

                self._last_position = f.tell()
        except Exception as e:
            logger.error(f"Consumer: Batch processing failed: {e}")

        return count

    def watch(self, interval: float = 1.0):
        """Monitor the stream continuously (Tail -f mode)."""
        logger.info(f"Consumer: Monitoring {self.stream_path}...")
        while True:
            processed = self.consume_batch()
            if processed > 0:
                logger.info(f"Consumer: Processed {processed} events.")
            time.sleep(interval)

    def _ingest_events(self, events: list[dict]):
        """Normalize and push events into the Kit Canonical Layer."""

        # v1.2.5: Use authoritative connection via brain
        with self.brain.get_connection() as conn:
            for event in events:
                event_type = event.get("type", "unknown")

                # --- [BRIDGE LAYER] Hard Structural Edges ---
                if event_type == "edge":
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO structure_edges 
                            (source_symbol, target_symbol, edge_type, language, confidence, source_file, line)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                event.get("source"),
                                event.get("target"),
                                event.get("relation"),
                                event.get("language"),
                                event.get("confidence", 1.0),
                                event.get("file"),
                                event.get("line"),
                            ),
                        )
                        logger.debug(f"Consumer: Ingested edge {event.get('source')} -> {event.get('target')}")
                    except Exception as e:
                        logger.error(f"Consumer: Edge ingestion failed: {e}")
                    continue

                # --- [COGNITIVE LAYER] Semantic Assimilation ---
                symbol = event.get("id") or event.get("symbol")
                path = event.get("path") or event.get("file")
                structural_hash = event.get("norm_hash")

                logger.debug(f"Consumer: Assimilating {event_type} at {path} (hash: {structural_hash})")

                try:
                    if hasattr(self.brain, "assimilate"):
                        self.brain.assimilate(
                            content=f"Structural Signal: {event_type} detected in {path}",
                            symbol=symbol,
                            metadata={
                                "source": "vantage",
                                "vantage_type": event_type,
                                "path": path,
                                "structural_hash": structural_hash,
                            },
                            structural_hash=structural_hash,
                        )
                except Exception as e:
                    logger.error(f"Consumer: Assimilation failed for {symbol}: {e}")


class VantageEventMock:
    """Helper to simulate Vantage outstream activity for testing."""

    @staticmethod
    def emit(stream_path: Path, event_type: str, symbol: str, path: str, structural_hash: str):
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        event = {"type": event_type, "id": symbol, "path": path, "norm_hash": structural_hash, "timestamp": time.time()}
        with open(stream_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
