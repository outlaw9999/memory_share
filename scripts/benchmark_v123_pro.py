import time
import random
import string
import json
import sys
import os
from collections import defaultdict
from pathlib import Path

# Add kit to path
sys.path.append(os.getcwd())

import kit.cli.auto_route as auto_route

# --- CHAOS DATA GENERATORS ---

def generate_noise():
    prefixes = ["I will ", "Here is ", "Output: ", "Done. ", "Ok, ", "Updated: "]
    return random.choice(prefixes) + "".join(random.choices(string.ascii_lowercase, k=15))

def generate_secret():
    # Mix common patterns with high entropy
    r = random.random()
    if r < 0.3:
        return "sk-" + "".join(random.choices(string.ascii_letters + string.digits, k=32))
    elif r < 0.6:
        return f"api_key = '{''.join(random.choices(string.ascii_letters + string.digits, k=24))}'"
    else:
        # Borderline case: suspicious keyword + entropy
        return f"Set your secret password to {''.join(random.choices(string.ascii_letters + string.digits, k=12))}"

def generate_global():
    return random.choice([
        "All database connections MUST strictly use connection pooling and NEVER use raw credentials.",
        "System architecture must enforce strict typing across all modules and mandatory validation.",
        "Security policy: Never expose internal IDs to the public API.",
        "Invariant: All write operations must be logged to the audit trail."
    ])

def generate_local():
    return random.choice([
        "Fixed the null pointer exception in auth.rs line 142.",
        "Adjusted the timeout in api.py for better resilience.",
        "Renamed variable 'x' to 'user_count' for readability in main.py.",
        "Added a null check for the config object in loader.py."
    ])

def generate_mixed():
    # Mixed intent: Noise + Global + Local + Secret
    return (
        "I will now fix this. "
        "Always validate input strictly. "
        "Fixed bug in auth.py line 42. "
        "token=" + "".join(random.choices(string.ascii_letters + string.digits, k=16))
    )

def generate_fake_global():
    # Bẫy Scorer: Có "Always" nhưng nội dung là "fix bug/file"
    return "Always fix bug in file main.py line 10"

def generate_dataset(n=1000):
    data = []
    for _ in range(n):
        r = random.random()
        if r < 0.2: data.append(("NOISE", generate_noise()))
        elif r < 0.4: data.append(("SECRET", generate_secret()))
        elif r < 0.6: data.append(("GLOBAL", generate_global()))
        elif r < 0.8: data.append(("LOCAL", generate_local()))
        elif r < 0.9: data.append(("MIXED", generate_mixed()))
        else: data.append(("FAKE_GLOBAL", generate_fake_global()))
    return data

# --- BENCHMARK ENGINE ---

def run_benchmark(n=10000):
    print(f"🚀 Initializing Chaos-Grade Benchmark v1.2.3 ({n} samples)")
    dataset = generate_dataset(n)
    
    stats = defaultdict(int)
    metrics = {
        "missed_secrets": 0,
        "false_blocks": 0,
        "noise_leak": 0,
        "wrong_global": 0, # LOCAL promoted to GLOBAL
        "wrong_local": 0,  # GLOBAL downgraded to LOCAL
    }

    start_time = time.perf_counter()

    for true_label, text in dataset:
        # Execution flow mimicking handle()
        
        # 1. Firewall (Security First)
        blocked, reason = auto_route.detect_secret(text)
        if blocked:
            stats["BLOCKED"] += 1
            if true_label not in ["SECRET", "MIXED"]:
                metrics["false_blocks"] += 1
            continue
        elif true_label in ["SECRET", "MIXED"]:
            metrics["missed_secrets"] += 1

        # 2. Noise (Hygiene Second)
        is_noise = auto_route.detect_noise(text)
        if is_noise:
            stats["DROPPED"] += 1
            continue
        elif true_label == "NOISE":
            metrics["noise_leak"] += 1

        # 3. Hash (CPU only)
        h = auto_route.sha256(auto_route.normalize(text))
        
        # 4. Score
        scores = auto_route.score(text)
        decision, conf = auto_route.decide(scores)
        
        # 5. Guard
        final = decision
        if decision == "GLOBAL" and conf < auto_route.CONF_THRESHOLD:
            final = "LOCAL"
            stats["DOWNGRADED"] += 1
        
        stats[f"ROUTED_{final}"] += 1
        
        # Accuracy Metrics
        if true_label == "GLOBAL" and final != "GLOBAL":
            metrics["wrong_local"] += 1
        if true_label in ["LOCAL", "FAKE_GLOBAL"] and final == "GLOBAL":
            metrics["wrong_global"] += 1

    end_time = time.perf_counter()
    total_ms = (end_time - start_time) * 1000
    avg_us = (total_ms / n) * 1000

    print("\n" + "="*40)
    print(f"📊 BENCHMARK RESULTS ({n} Req)")
    print("="*40)
    print(f"⏱️  Total Time: {total_ms:.2f} ms")
    print(f"⚡ Avg Latency: {avg_us:.2f} µs/req")
    
    print("\n🛡️  ROUTING STATS:")
    for k, v in sorted(stats.items()):
        print(f"  - {k}: {v}")
        
    print("\n🧠 COGNITIVE PRECISION:")
    print(f"  - Missed Secrets: {metrics['missed_secrets']}")
    print(f"  - False Blocks: {metrics['false_blocks']}")
    print(f"  - Wrong Global (Infection): {metrics['wrong_global']}")
    print(f"  - Wrong Local (Downgrade): {metrics['wrong_local']}")
    print(f"  - Noise Leak: {metrics['noise_leak']}")
    print("="*40)
    
    if metrics["wrong_global"] > 0:
        print("❌ STATUS: FAIL (Global Brain Infection Detected)")
    elif metrics["missed_secrets"] > 0:
        print("⚠️  STATUS: WARN (Secret Leak Risk)")
    else:
        print("✅ STATUS: PASS (Governance Hardened)")

if __name__ == "__main__":
    run_benchmark(10000)
