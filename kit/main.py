#!/usr/bin/env python3
"""
Antigravity .kit CLI - Unified Cognitive OS Entry Point.
This file is now a thin facade to maintain backward compatibility (python -m kit.main).
Logic has been moved to kit/cli/main.py to enforce architectural layering.
"""
from .cli.main import main

if __name__ == "__main__":
    main()
