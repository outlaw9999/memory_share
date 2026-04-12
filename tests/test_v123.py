# Python >= 3.14 (code-py-314 compliant)
import json
import os
import sys
from pathlib import Path

# Add kit to path
sys.path.append(os.getcwd())

import kit.cli.auto_route as auto_route

TEST_FILE: Path = Path("tests/test_cases.jsonl")
SEEN_HASHES: set[str] = set()


def is_duplicate_mock(h: str) -> bool:
    if h in SEEN_HASHES:
        return True
    SEEN_HASHES.add(h)
    return False


def evaluate_case(text: str, check_dup=False) -> str:
    # 0. Strip / Clean
    # (Optional: auto_route already does this inside detect_secret,
    # but we follow the logic flow of handle())

    # 1. Noise
    if auto_route.detect_noise(text):
        return "DROP"

    # 2. Firewall
    blocked, _ = auto_route.detect_secret(text)
    if blocked:
        return "BLOCK"

    # 3. Hash
    normalized = auto_route.normalize(text)
    h = auto_route.sha256(normalized)

    if check_dup and is_duplicate_mock(h):
        return "SKIP"

    # If not check_dup, we still "seed" the mock for idempotency tests
    if not check_dup:
        is_duplicate_mock(h)

    # 4. Scorer
    scores = auto_route.score(text)
    decision, conf = auto_route.decide(scores)

    # 5. Guard
    if decision == "GLOBAL" and conf < auto_route.CONF_THRESHOLD:
        return "LOCAL"

    return decision


def run_precision_test() -> None:
    print("\n=== PRECISION REPORT ===")
    total = 0
    correct = 0

    if not TEST_FILE.exists():
        print(f"Error: {TEST_FILE} not found.")
        return

    with TEST_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            result = evaluate_case(item["input"])

            total += 1
            if result == item["expected"]:
                correct += 1
                print(f"[PASS] Expected: {item['expected']} -> {item['input'][:40]}...")
            else:
                print(f"[FAIL] {item['input'][:50]}...")
                print(f"  Expected: {item['expected']}, Got: {result}")

    accuracy = (correct / total * 100) if total > 0 else 0
    print("-" * 30)
    print(f"Final Accuracy: {accuracy:.2f}% ({correct}/{total})")


def run_idempotency_test() -> None:
    print("\n=== IDEMPOTENCY TEST (Fixed Hallucination) ===")
    text = "All systems MUST enforce strict typing and follow architecture patterns."

    # Reset seen hashes for clean test
    SEEN_HASHES.clear()

    for i in range(1, 6):
        result = evaluate_case(text, check_dup=True)
        print(f"Run {i}: {result}")


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    run_precision_test()
    run_idempotency_test()
