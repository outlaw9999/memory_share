import argparse
import json
import socket
import sys
from pathlib import Path

from kit.core.kit_platform import read_stdin_fail_fast, FAST_TIMEOUT


def is_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    """Fast TCP probe to verify if a provider port is alive."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, socket.timeout, socket.error):
        return False


from kit_agent.core.cache import SemanticCache
from kit_agent.core.metrics import MetricsPersistence, ModelMetrics
from kit_agent.core.protocol import AMSBProtocol
from kit_agent.core.router import ModelRouter
from kit_agent.core.output_contract import normalize_output_contract
from kit_agent.providers.gemini import GeminiProvider
from kit_agent.providers.local import LocalLLMProvider
from kit_agent.providers.mock import MockChaosProvider
from kit_agent.providers.semantic_mock import SemanticMockProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="kit-agent (AMSB v1.2.0 GA): Production-grade AI orchestrator")
    parser.add_argument("--db", help="Path to the project database (overrides default)")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", aliases=["ask"], help="Run a task through the AMSB loop")
    run_parser.add_argument("task", help="The architectural or coding task to perform")
    run_parser.add_argument("--type", choices=["general", "simple", "refactor", "critical"], default="general")
    run_parser.add_argument("--mode", choices=["strict", "advisory", "silent"], default="strict")
    run_parser.add_argument("--provider", help="Force a specific provider (e.g., local, gemini, mock)")
    run_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")

    recall_parser = subparsers.add_parser("recall", help="Recall context from memory")
    recall_parser.add_argument("entities", nargs="+", help="Entities or tags to recall")
    recall_parser.add_argument("--limit", type=int, default=10, help="Max number of items to recall")

    subparsers.add_parser("status", help="Show agent health and trust metrics")
    subparsers.add_parser("stats", help="Alias for status")
    subparsers.add_parser("reset-metrics", help="Reset persisted agent metrics")

    args = parser.parse_args()

    import kit.api as api

    db_path = Path(args.db).absolute() if args.db else None
    api.init_kernel(db_path)
    _, project_db, _ = api.resolve_paths()
    persistence = MetricsPersistence(project_db)

    metrics = {
        "gemini": ModelMetrics(name="gemini", cost_per_1k=0.001),
        "local": ModelMetrics(name="local", cost_per_1k=0.0),
        "mock": ModelMetrics(name="mock", cost_per_1k=0.0),
        "semantic_mock": ModelMetrics(name="semantic_mock", cost_per_1k=0.0),
    }
    metrics = persistence.load_all(metrics)

    router = ModelRouter(metrics, persistence=persistence)
    cache = SemanticCache()

    # v1.2.1 Hotfix: Default to 'gemini' and probe 'local' to avoid 300s timeout.
    local_alive = is_port_open("127.0.0.1", 1337)
    forced_provider = getattr(args, "provider", None)

    if forced_provider == "local" and not local_alive:
        print("\033[91m[ERROR] Local provider (Jan) unreachable on port 1337. Aborting.\033[0m")
        sys.exit(1)

    providers = {
        "gemini": GeminiProvider(),
        "local": LocalLLMProvider(),
        "mock": MockChaosProvider(failure_rate=0.4),
        "semantic_mock": SemanticMockProvider(),
    }

    # If using discovery (no forced provider), and local is dead, remove it from
    # the active pool to prevent the router from even trying it.
    if not forced_provider and not local_alive:
        del providers["local"]

    protocol = AMSBProtocol(router, providers, cache)

    if args.command in {"run", "ask"}:
        ephemeral_data = None
        ephemeral_data_raw = read_stdin_fail_fast(timeout=FAST_TIMEOUT)
        if ephemeral_data_raw:
            try:
                # Try to parse as JSON for structure, otherwise keep as raw text
                try:
                    ephemeral_data = json.loads(ephemeral_data_raw)
                    ephemeral_data = json.dumps(ephemeral_data, indent=2)
                except json.JSONDecodeError:
                    ephemeral_data = ephemeral_data_raw
            except Exception as e:
                print(f"[WARN] Failed to process stdin: {e}", file=sys.stderr)

        result_raw = protocol.run(
            args.task, task_type=args.type, forced_provider=args.provider, ephemeral_data=ephemeral_data
        )

        try:
            data = normalize_output_contract(result_raw)
        except (ValueError, TypeError):
            if not args.json:
                print(f"[AGENT] kit-agent starting task: {args.task}")
            print(result_raw)
            sys.exit(2)

        if args.json:
            print(json.dumps(data, sort_keys=True))
            return

        print(f"[AGENT] kit-agent starting task: {args.task}")
        print("\n" + "=" * 60)
        print("AGENT COGNITIVE REPORT")
        print("=" * 60)
        print(f"DECISION:   {data['decision']}")
        print(f"CONFIDENCE: {data['confidence']:.2f}")
        print(f"REASON:     {data['reason']}")

        provider = data.get("provider")
        if provider:
            print(f"PROVIDER:   {provider}")

        if data.get("violations"):
            print("VIOLATIONS:")
            for item in data["violations"]:
                print(f"- {item}")

        if data.get("suggestions"):
            print("SUGGESTIONS:")
            for item in data["suggestions"]:
                print(f"- {item}")

        if data.get("content"):
            print("CONTENT:")
            print(data["content"])

        print("=" * 60 + "\n")

        # Standardized Exit Codes: BLOCK=1, PASS/WARN=0
        if data["decision"] == "BLOCK":
            sys.exit(1)
    elif args.command == "recall":
        print(f"[RECALL] Recalling context for: {', '.join(args.entities)}")
        facts = api.recall(args.entities, limit=args.limit)
        if not facts:
            print("No items found in memory.")
        for i, fact in enumerate(facts, 1):
            print(f"{i}. [{fact.get('kind', 'fact')}] {fact.get('content')}")
    elif args.command in {"status", "stats"}:
        print("[STATUS] kit-agent Engine Status:")
        for name, model_metrics in metrics.items():
            trust = model_metrics.get_effective_trust()
            status = "HEALTHY" if model_metrics.healthy else "DEGRADED (Cooldown)"
            print(f"- {name:8}: {status:20} Trust: {trust:.4f} Latency: {model_metrics.avg_latency:.2f}s")
    elif args.command == "reset-metrics":
        import sqlite3

        with sqlite3.connect(project_db, timeout=1.0) as conn:
            conn.execute("DROP TABLE IF EXISTS agent_metrics")
        print("Agent metrics reset. SQLite metrics table cleared.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
