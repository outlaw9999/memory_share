"""Vantage executor for dispatcher."""
import subprocess
import sys
import logging

logger = logging.getLogger("kit.vantage_dispatch")

VANTAGE_BINARY = "E:\\DEV\\opensource_contrib\\Vantage\\target\\release\\kit-vantage.exe"


def run_vantage(command: str, args) -> int:
    """Direct Vantage execution without reasoning."""
    subcommands = {
        "graph": "extract-edges",
        "blast": "blast",
        "impact": "impact",
    }
    
    subcmd = subcommands.get(command, command)
    target = getattr(args, "target", None) or getattr(args, "module", None)
    if target is None:
        positionals = [part for part in sys.argv[2:] if not part.startswith("-")]
        target = positionals[0] if positionals else "."
    
    try:
        result = subprocess.run(
            [VANTAGE_BINARY, subcmd, str(target)],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    except Exception as e:
        logger.error(f"Vantage execution failed: {e}")
        return 1
