# kit/cih/runtime_injector.py

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any, Dict, Optional

from kit.cih.cognitive_translator import CIHCognitiveTranslator
from kit.cih.signal_extractor import CIHSignalExtractor

from kit.core.memory_router import MemoryRouter


class CIHWriteGate:
    """
    CIH Enforcement Gate for writes.
    Ensures all signals are tagged and routed through the authorized policy.
    """
    def __init__(self, router: MemoryRouter):
        self.router = router

    def write(self, request: Any) -> None:
        # Enforce metadata tagging for provenance
        request.source_metadata["cih_enforced"] = True
        
        # ALL WRITES MUST GO THROUGH AUTHORIZED ROUTER PATH
        self.router.route_write(request)


class CIHRuntimeInjector:
    """
    Lock-free (practically), bounded, drop-safe CIH pipeline.

    DESIGN GOALS:
    - NEVER block Vantage runtime
    - NEVER crash host system
    - Drop oldest under pressure (backpressure shield)
    """

    def __init__(
        self,
        router: MemoryRouter,
        max_buffer: int = 256,
        drop_policy: str = "oldest"  # or "newest"
    ):
        self.router = router
        self.buffer = deque(maxlen=max_buffer)
        self.lock = Lock()
        self.drop_policy = drop_policy

        # Initialize Gate
        self.gate = CIHWriteGate(router)
        
        # Keep instances for translation
        self.extractor = CIHSignalExtractor()
        self.translator = CIHCognitiveTranslator()

    # -----------------------------
    # CORE ENTRYPOINT
    # -----------------------------
    def post(self, event: dict[str, Any]) -> None:
        """
        Fire-and-forget ingestion.
        Guaranteed non-blocking.
        """

        try:
            self._enqueue(event)
        except Exception:
            # ABSOLUTE SILENCE GUARANTEE
            pass

    # -----------------------------
    # BUFFER LAYER
    # -----------------------------
    def _enqueue(self, event: dict[str, Any]) -> None:
        with self.lock:
            # deque(maxlen) auto-drops oldest -> backpressure safety
            self.buffer.append(event)

    # -----------------------------
    # DRAIN PIPELINE (called async or background thread)
    # -----------------------------
    def drain(self, batch_size: int = 32) -> None:
        """
        Converts buffered events -> memory writes.
        Should be called by scheduler / background worker.
        """

        batch = []

        with self.lock:
            while self.buffer and len(batch) < batch_size:
                batch.append(self.buffer.popleft())

        for event in batch:
            try:
                signal = self.extractor.extract(event)
                request = self.translator.translate(signal)
                
                # ENFORCED: Must go through the gate
                self.gate.write(request)
            except Exception:
                # NEVER block pipeline
                continue
