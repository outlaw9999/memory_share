#!/usr/bin/env python3
"""
Antigravity .kit CLI - Unified Cognitive OS Entry Point.
This file is now a thin facade to maintain backward compatibility (python -m kit.main).
Logic has been moved to kit/cli/main.py to enforce architectural layering.
"""

# .kit V1: Agent Knowledge Kernel
# Modified for V1.3
import sys
from kit.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
