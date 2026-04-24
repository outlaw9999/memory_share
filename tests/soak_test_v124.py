import sys
import json
import time
import random
from pathlib import Path

# Add project root to sys.path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

import kit.api as api
from kit.core.vantage_stream_consumer import VantageStreamConsumer

def run_soak_test(iterations=100, batch_size=50):
    print(f"Starting Soak Test v1.2.4-RC1 ({iterations} iterations, batch_size={batch_size})")
    
    api.init_kernel(mode="isolated")
    brain = api.get_brain()
    stream_path = brain.root_path / ".vantage" / "soak_stream.jsonl"
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    
    consumer = VantageStreamConsumer(brain, stream_path=stream_path)
    
    total_edges = 0
    start_time = time.time()
    
    try:
        for i in range(iterations):
            # 1. Generate random structural data
            events = []
            for j in range(batch_size):
                if random.random() > 0.3:
                    # Edge
                    events.append({
                        "type": "edge",
                        "source": f"Symbol_{random.randint(1, 1000)}",
                        "target": f"Symbol_{random.randint(1, 1000)}",
                        "relation": random.choice(["CALLS", "IMPORTS", "INHERITS"]),
                        "v": "1.2.4"
                    })
                else:
                    # Node/Observation
                    events.append({
                        "type": "function",
                        "id": f"Func_{random.randint(1, 1000)}",
                        "path": f"src/module_{random.randint(1, 10)}.py",
                        "v": "1.2.4"
                    })
            
            # Inject a corrupted line occasionally
            with open(stream_path, "a", encoding="utf-8") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")
                if i % 10 == 0:
                    f.write('{"invalid": json... corrupted\n')
            
            # 2. Consume
            processed = consumer.consume_batch()
            total_edges += processed
            
            if i % 20 == 0:
                print(f"  Iteration {i}/{iterations}: Processed {total_edges} events so far...")
                
    except Exception as e:
        print(f"FAILED: Soak test error at iteration {i}: {e}")
        sys.exit(1)
        
    duration = time.time() - start_time
    print(f"\nSUCCESS: Soak test completed.")
    print(f"  Total events: {total_edges}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Throughput: {total_edges/duration:.2f} events/s")

if __name__ == "__main__":
    run_soak_test(iterations=100, batch_size=100)
