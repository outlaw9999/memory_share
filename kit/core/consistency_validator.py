"""Cross-layer consistency checks for policy, execution, and observability."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from kit.core.command_registry import registry
from kit.core.command_routes import COMMANDS
from kit.core.execution_trace import OBSERVABILITY_COMMANDS
from kit.core.kit_env import get_vantage_bin

TOP_LEVEL_PARSER_RE = re.compile(
    r"^\s*(?:(?P<var>\w+)\s*=\s*)?subparsers\.add_parser\(\"(?P<command>[^\"]+)\"",
    re.MULTILINE,
)
PARSER_OPTION_RE = re.compile(
    r"^\s*(?P<var>\w+)\.add_argument\((?P<quote>['\"])(?P<option>[^'\"]+)(?P=quote)",
    re.MULTILINE,
)
POLICY_RUNTIME_RE = re.compile(r"\bkit(?:-vantage)?\s+[a-z][\w-]*", re.IGNORECASE)


def _cli_main_path() -> Path:
    return Path(__file__).resolve().parents[1] / "cli" / "main.py"


def _agents_path() -> Path:
    return Path(__file__).resolve().parents[2] / "AGENTS.md"


def _parse_cli_surface(source_text: str) -> dict[str, dict[str, Any]]:
    """Extract top-level parser commands and their option flags from CLI source."""
    parser_vars: dict[str, str] = {}
    commands: dict[str, dict[str, Any]] = {}

    for match in TOP_LEVEL_PARSER_RE.finditer(source_text):
        command = match.group("command")
        commands.setdefault(command, {"options": []})
        parser_var = match.group("var")
        if parser_var:
            parser_vars[parser_var] = command

    for match in PARSER_OPTION_RE.finditer(source_text):
        parser_var = match.group("var")
        option = match.group("option")
        command = parser_vars.get(parser_var)
        if not command or not option.startswith("--"):
            continue
        commands[command]["options"].append(option)

    for command in commands:
        commands[command]["options"] = sorted(set(commands[command]["options"]))

    return commands


def _read_vantage_capabilities() -> dict[str, Any]:
    """Probe the installed Vantage binary for supported subcommands."""
    vantage_bin = get_vantage_bin()
    if not vantage_bin or not vantage_bin.exists():
        return {"binary": "missing", "commands": []}

    try:
        if vantage_bin.stat().st_size < 1_000_000:
            return {
                "binary": str(vantage_bin),
                "commands": [],
                "skipped": "shim_binary",
            }
    except OSError as exc:
        return {
            "binary": str(vantage_bin),
            "commands": [],
            "error": str(exc),
        }

    try:
        result = subprocess.run(
            [str(vantage_bin), "--help"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except Exception as exc:
        return {
            "binary": str(vantage_bin),
            "commands": [],
            "error": str(exc),
        }

    commands: list[str] = []
    in_commands = False
    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped == "Commands:":
            in_commands = True
            continue
        if not in_commands:
            continue
        if not stripped:
            continue
        if stripped.startswith("Options:"):
            break
        name = stripped.split()[0]
        if name and name != "help":
            commands.append(name)

    return {
        "binary": str(vantage_bin),
        "commands": sorted(set(commands)),
        "ok": result.returncode == 0,
    }


def summarize_consistency(
    *,
    routes: dict[str, dict[str, str]] | None = None,
    cli_surface: dict[str, dict[str, Any]] | None = None,
    registry_commands: set[str] | None = None,
    observability_commands: set[str] | None = None,
    policy_text: str | None = None,
    vantage_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize cross-layer drift across policy, execution, and observability."""
    import kit.cli.main  # noqa: F401

    routes = routes or COMMANDS
    observability_commands = observability_commands or set(OBSERVABILITY_COMMANDS)
    registry_commands = registry_commands or {command.name for command in registry.list_commands()}

    if cli_surface is None:
        cli_source_path = _cli_main_path()
        cli_surface = _parse_cli_surface(cli_source_path.read_text(encoding="utf-8"))
    else:
        cli_source_path = None

    if policy_text is None:
        agents_path = _agents_path()
        policy_text = agents_path.read_text(encoding="utf-8")
    else:
        agents_path = None

    if vantage_capabilities is None:
        vantage_capabilities = _read_vantage_capabilities()

    route_commands = set(routes)
    cli_commands = set(cli_surface)
    direct_commands = sorted(command for command, route in routes.items() if route.get("mode") == "direct")
    routed_commands = sorted(command for command, route in routes.items() if route.get("mode") == "routed")
    diagnostic_commands = sorted(command for command, route in routes.items() if route.get("mode") == "diagnostic")

    missing_cli_surface = sorted(route_commands - cli_commands)
    parser_fallback_missing = sorted(
        command
        for command in direct_commands
        if cli_surface.get(command, {}).get("options") and command not in registry_commands
    )
    observability_overlap = sorted(route_commands & observability_commands)
    policy_runtime_lines = [
        line.strip()
        for line in policy_text.splitlines()
        if POLICY_RUNTIME_RE.search(line)
    ]

    supported_vantage_commands = set(vantage_capabilities.get("commands", []))
    unsupported_vantage_mappings = []
    route_aliases = []
    for command, route in sorted(routes.items()):
        executor = route.get("executor")
        if executor != "vantage":
            continue
        mapped = command
        if command == "graph":
            mapped = "extract-edges"
        if mapped not in supported_vantage_commands:
            unsupported_vantage_mappings.append(
                {
                    "command": command,
                    "mapped_subcommand": mapped,
                }
            )
        elif mapped != command and command in registry_commands:
            route_aliases.append(
                {
                    "command": command,
                    "mapped_subcommand": mapped,
                }
            )

    issues: list[dict[str, Any]] = []
    if missing_cli_surface:
        issues.append({"kind": "missing_cli_surface", "commands": missing_cli_surface})
    if parser_fallback_missing:
        issues.append({"kind": "missing_parser_fallback_handler", "commands": parser_fallback_missing})
    if observability_overlap:
        issues.append({"kind": "observability_self_noise_overlap", "commands": observability_overlap})
    if policy_runtime_lines:
        issues.append({"kind": "policy_runtime_reference", "lines": policy_runtime_lines})
    if unsupported_vantage_mappings:
        issues.append({"kind": "unsupported_vantage_mapping", "items": unsupported_vantage_mappings})
    if route_aliases:
        issues.append({"kind": "direct_route_alias_drift", "items": route_aliases})

    return {
        "ok": not issues,
        "routes_checked": len(routes),
        "route_modes": {
            "direct": direct_commands,
            "routed": routed_commands,
            "diagnostic": diagnostic_commands,
        },
        "cli_surface": {
            "source": str(cli_source_path) if cli_source_path else "injected",
            "command_count": len(cli_surface),
            "commands": {command: cli_surface[command]["options"] for command in sorted(cli_surface)},
        },
        "registry": {
            "command_count": len(registry_commands),
            "commands": sorted(registry_commands),
        },
        "policy": {
            "source": str(agents_path) if agents_path else "injected",
            "runtime_references": policy_runtime_lines,
        },
        "observability": {
            "commands": sorted(observability_commands),
            "self_noise_overlap": observability_overlap,
        },
        "vantage": vantage_capabilities,
        "issues": issues,
    }


if __name__ == "__main__":
    print(json.dumps(summarize_consistency(), indent=2))
