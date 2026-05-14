# kit/cli/adaptive_trainer.py
# v1.2.5 - Statistical Weight Correction Engine

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from kit.core.memory_topology import MemoryTopologyFactory
# v1.2.5-TITANIUM: Resolve telemetry path via authoritative topology
_topo = MemoryTopologyFactory.for_project(Path.cwd())
TELEMETRY_PATH = _topo.resolve("global", "audit")


def run_trainer():
    if not TELEMETRY_PATH.exists():
        print("No telemetry found. Start dogfooding first.")
        return

    print("[TRAINER] v1.2.5 Adaptive Scorer Trainer Initialized")

    stats: defaultdict[str, int] = defaultdict(int)
    feedback_count = 0
    corrections: list[dict[str, Any]] = []

    with open(TELEMETRY_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("status") == "OK":
                    stats[data["route"]] += 1
                elif data.get("type") == "FEEDBACK":
                    feedback_count += 1
                    corrections.append(data)
            except Exception:
                continue

    print("-" * 30)
    print(f"Stats: GLOBAL={stats['GLOBAL']}, LOCAL={stats['LOCAL']}")
    print(f"Feedback entries: {feedback_count}")

    if feedback_count == 0:
        print("\n[ADVICE] System behavior is consistent. No weighting changes suggested yet.")
        return

    # Logic for weight delta calculation based on correction patterns
    # (In v1.2.5 this will propose changes to GLOBAL_KW/LOCAL_KW weights)
    print("\n[v1.2.5 PROPOSAL]")
    for c in corrections:
        correction: dict[str, Any] = c
        print(f"  - Correction: Obs {correction['obs_id']} should be {correction['correct_label']}")

    print("\nRecommendation: Dogfood more data to reach statistical significance (min 50 feedbacks).")


if __name__ == "__main__":
    run_trainer()
