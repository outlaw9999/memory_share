# kit/__main__.py — v1.2.5-LOCK: CANONICAL ENTRYPOINT
#
# INVARIANT: This is the ONLY valid execution path for all kit operations.
# All tests, scripts, and user invocations MUST use `python -m kit` or `kit CLI`.
#
# Execution topology:
#   python -m kit      → This file → kit.cli.main:main  [CANONICAL]
#   python kit.py      → Redirects to python -m kit      [LEGACY WRAPPER]
#   kit CLI (installed)→ Points to kit.cli.main:main    [CANONICAL]

from kit.cli.main import main

if __name__ == "__main__":
    main()
