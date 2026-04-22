"""Vantage Stream Consumer (Stage 5.5.1).

Responsible for consuming structural event streams from Vantage.
Decouples perception (Vantage) from cognition (Kit).
"""

from __future__ import annotations
import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Generator

if TYPE_CHECKING:
    from kit.core.kit_cognitive_core import SAMBrain

logger = logging.getLogger("kit.vantage_consumer")

class VantageStreamConsumer:
    """Consumes JSONL events from .vantage/outstream.jsonl."""
    
    def __init__(self, brain: SAMBrain, stream_path: Optional[Path] = None):
        self.brain = brain
        self.stream_path = stream_path or brain.root_path / ".vantage" / "outstream.jsonl"
        self._last_position = 0

    def consume_batch(self) -> int:
        """Process all pending events in the stream."""
        if not self.stream_path.exists():
            return 0
            
        count = 0
        try:
            with open(self.stream_path, "r", encoding="utf-8") as f:
                # Seek to last known position to support incremental processing
                f.seek(self._last_position)
                
                events = []
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        events.append(event)
                        count += 1
                    except json.JSONDecodeError as e:
                        logger.warning(f"Consumer: Skipping invalid JSON line: {e}")
                
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

    def _ingest_events(self, events: List[Dict]):
        """Normalize and push events into the Kit Ingestion Buffer."""
        # This will be integrated with kit_ingestion_buffer.py in the next step
        # For now, we simulate the 'assimilation' process
        for event in events:
            # Vantage Event Schema (v1.2.4 Standard):
            # { "type": "function", "id": "uuid", "norm_hash": "...", "path": "..." }
            
            event_type = event.get("type", "unknown")
            symbol = event.get("id")  # In Vantage v1.2.4, 'id' is the symbol
            path = event.get("path")
            structural_hash = event.get("norm_hash")
            
            # Assimilation logic:
            # We don't 'learn' it like a human fact, we 'assimilate' it as a structural truth.
            logger.debug(f"Consumer: Assimilating {event_type} at {path} (hash: {structural_hash})")
            
            # Integration with Brain.assimilate() (to be implemented in kit_cognitive_core.py)
            try:
                if hasattr(self.brain, "assimilate"):
                    self.brain.assimilate(
                        content=f"Structural Signal: {event_type} detected in {path}",
                        symbol=symbol,
                        metadata={
                            "source": "vantage",
                            "vantage_type": event_type,
                            "path": path,
                            "structural_hash": structural_hash
                        },
                        structural_hash=structural_hash
                    )
            except Exception as e:
                logger.error(f"Consumer: Assimilation failed for {symbol}: {e}")

class VantageEventMock:
    """Helper to simulate Vantage outstream activity for testing."""
    @staticmethod
    def emit(stream_path: Path, event_type: str, symbol: str, path: str, structural_hash: str):
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "type": event_type,
            "id": symbol,
            "path": path,
            "norm_hash": structural_hash,
            "timestamp": time.time()
        }
        with open(stream_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
