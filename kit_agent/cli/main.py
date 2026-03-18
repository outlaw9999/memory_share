import argparse

from kit_agent.core.cache import SemanticCache
from kit_agent.core.metrics import MetricsPersistence, ModelMetrics
from kit_agent.core.protocol import AMSBProtocol
from kit_agent.core.router import ModelRouter
from kit_agent.providers.gemini import GeminiProvider
from kit_agent.providers.local import LocalLLMProvider
from kit_agent.providers.mock import MockChaosProvider
from kit_agent.providers.semantic_mock import SemanticMockProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="kit-agent (AMSB v1.1 Stable): Production-grade AI orchestrator")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", aliases=["ask"], help="Run a task through the AMSB loop")
    run_parser.add_argument("task", help="The architectural or coding task to perform")
    run_parser.add_argument("--type", choices=["general", "simple", "refactor", "critical"], default="general")
    run_parser.add_argument("--mode", choices=["strict", "advisory", "silent"], default="strict")
    run_parser.add_argument("--provider", help="Force a specific provider (e.g., local, gemini, mock)")

    recall_parser = subparsers.add_parser("recall", help="Recall context from memory")
    recall_parser.add_argument("entities", nargs="+", help="Entities or tags to recall")
    recall_parser.add_argument("--limit", type=int, default=10, help="Max number of items to recall")

    subparsers.add_parser("status", help="Show agent health and trust metrics")
    subparsers.add_parser("stats", help="Alias for status")
    subparsers.add_parser("reset-metrics", help="Reset persisted agent metrics")

    args = parser.parse_args()

    import kit.api as api

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

    providers = {
        "gemini": GeminiProvider(),
        "local": LocalLLMProvider(),
        "mock": MockChaosProvider(failure_rate=0.4),
        "semantic_mock": SemanticMockProvider(),
    }

    protocol = AMSBProtocol(router, providers, cache)

    if args.command in {"run", "ask"}:
        print(f"[AGENT] kit-agent starting task: {args.task}")
        result = protocol.run(args.task, task_type=args.type, forced_provider=args.provider)
        print("\n--- RESULT ---")
        print(result)
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

        with sqlite3.connect(project_db, timeout=5.0) as conn:
            conn.execute("DROP TABLE IF EXISTS agent_metrics")
        print("Agent metrics reset. SQLite metrics table cleared.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
