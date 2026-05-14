# tests/harness/policy_runner.py

import json
from typing import List, Dict, Any
from kit.core.memory_policy import MemoryPolicy

class PolicyTestHarness:
    """
    Deterministic Contract Executor for Kit v1.2.5.
    Validates MemoryPolicy against the Golden Truth Dataset.
    """
    
    @staticmethod
    def run_golden_suite(dataset_path: str) -> List[Dict[str, Any]]:
        results = []
        with open(dataset_path, "r") as f:
            for line in f:
                case = json.loads(line)
                
                # Convert dicts to mock memory objects
                candidates = []
                for m in case["memories"]:
                    # Create a mock object with attributes
                    mock_m = type('Memory', (object,), m)()
                    candidates.append(mock_m)
                
                winner = MemoryPolicy.resolve(candidates)
                actual_winner_tier = getattr(winner, 'brain_source', 'none') if winner else 'none'
                actual_content = getattr(winner, 'content', 'none') if winner else 'none'
                
                # Evaluation
                success = False
                if case["expected_winner"] in ("frozen", "global", "local"):
                    success = (actual_winner_tier == case["expected_winner"])
                else:
                    success = (actual_content == case["expected_winner"])
                
                results.append({
                    "id": case["id"],
                    "intent": case["intent"],
                    "pass": success,
                    "actual_tier": actual_winner_tier,
                    "actual_content": actual_content
                })
        return results
