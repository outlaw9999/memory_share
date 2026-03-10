import os
import sys
import time
from pathlib import Path

# Mock token count (4 chars = 1 token)
def count_tokens(text: str) -> int:
    return len(text) // 4

def benchmark():
    print("--- .kit Context Compression Benchmark ---")
    root = Path(".")
    py_files = list(root.rglob("*.py"))
    
    # 1. Baseline: Raw Files
    raw_content = ""
    for f in py_files[:20]: # Sample 20 files
        raw_content += f.read_text(errors="ignore")
    
    raw_tokens = count_tokens(raw_content)
    print(f"Baseline (Raw Files): {raw_tokens:,} tokens")
    
    # 2. Graph Slice (Simulated)
    # In practice, this would call 'kit context Symbol'
    slice_content = "def sample_function():\n    pass\n" * 10
    slice_tokens = count_tokens(slice_content)
    print(f"Graph Slice:         {slice_tokens:,} tokens")
    
    # 3. Signal Envelope (Simulated)
    signal_content = "Symbol 'X' has high gravity; 5 callers affected."
    signal_tokens = count_tokens(signal_content)
    print(f"Signal Envelope:    {signal_tokens:,} tokens")
    
    print("-" * 40)
    compression = raw_tokens / signal_tokens
    print(f"Total Compression:  {compression:,.1f}x")
    print("------------------------------------------")

if __name__ == "__main__":
    benchmark()
