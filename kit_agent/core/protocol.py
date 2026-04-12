import time
from typing import Any

import kit.api as kit_api
from kit_agent.core.cache import SemanticCache
from kit_agent.core.output_contract import (
    OutputContractError,
    normalize_output_contract,
    serialize_output_contract,
)
from kit_agent.core.router import ModelRouter
from kit_agent.utils.process import safe_run


class AMSBProtocol:
    def __init__(self, router: ModelRouter, providers: dict[str, Any], cache: SemanticCache):
        self.router = router
        self.providers = providers
        self.cache = cache

    def _get_context_hash(self, context_text: str) -> str:
        import hashlib

        return hashlib.md5(context_text.encode()).hexdigest()

    def _finalize_output(self, model_name: str, output_text: str) -> str:
        payload = normalize_output_contract(output_text)
        payload["provider"] = model_name
        return serialize_output_contract(payload)

    def _format_memory_context(self, memories: list[Any]) -> str:
        lines: list[str] = []
        for memory in memories[:3]:
            # Semantic Unit: Try to keep the first complete sentence/line
            # Do not truncate invariants aggressively
            content = memory.content.splitlines()[0].strip()

            # Simple rule: If invariant, keep up to 200 chars to ensure context
            # Non-invariants get 100 char 'compact' mode
            limit = 200 if getattr(memory, "tag", "decision") == "invariant" else 100

            if len(content) > limit:
                content = content[: limit - 3] + "..."

            if content:
                lines.append(f"- {content}")
        return "\n".join(lines[:3])

    def _memory_matches_task(self, task: str, memories: list[Any]) -> bool:
        stop_words = {"what", "about", "with", "from", "into", "this", "that", "design"}
        raw_terms = [term.lower() for term in task.replace(".", " ").replace("?", " ").split() if len(term) >= 4]
        task_terms = {variant for term in raw_terms if term not in stop_words for variant in self._term_variants(term)}
        if not task_terms:
            return bool(memories)

        for memory in memories:
            memory_terms = {
                variant
                for token in memory.content.lower().replace(".", " ").replace("?", " ").split()
                if len(token) >= 4
                for variant in self._term_variants(token)
            }
            if task_terms & memory_terms:
                return True
        return False

    def _normalize_term(self, term: str) -> str:
        normalized = "".join(ch for ch in term.lower() if ch.isalnum())
        for suffix in ("ingly", "ing", "ers", "er", "ed", "es", "s"):
            if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 3:
                return normalized[: -len(suffix)]
        return normalized

    def _term_variants(self, term: str) -> set[str]:
        normalized = self._normalize_term(term)
        variants = {normalized}
        if normalized.endswith("e") and len(normalized) >= 4:
            variants.add(normalized[:-1])
        else:
            variants.add(f"{normalized}e")
        return variants

    def _load_memory_context(self, task: str) -> str:
        assessment = kit_api.recall_with_assessment([], limit=3, here=True, fast=True)
        if (
            assessment.memories
            and assessment.status == "WEAK_SIGNAL"
            and any(getattr(memory, "tag", "") == "invariant" for memory in assessment.memories)
        ):
            assessment = type(assessment)(
                memories=assessment.memories,
                confidence=max(assessment.confidence, 0.9),
                status="HIGH_CONFIDENCE",
            )

        if (
            assessment.memories
            and assessment.status != "AMBIGUOUS"
            and not self._memory_matches_task(task, assessment.memories)
        ):
            try:
                search_results = kit_api.search(task, limit=3, fast=True)
                if search_results:
                    assessment = kit_api.get_brain().assess_ranked_memories(search_results)
                else:
                    # If ambient memory does not match task and search finds nothing relevant, omit memory block.
                    assessment = type(assessment)(memories=[], confidence=0.0, status="EMPTY")
            except (KeyError, ValueError, AttributeError):
                assessment = type(assessment)(memories=[], confidence=0.0, status="EMPTY")

        if assessment.status == "EMPTY" or not assessment.memories:
            return ""
        formatted_rules = self._format_memory_context(assessment.memories)
        if not formatted_rules:
            return ""
        if assessment.status == "HIGH_CONFIDENCE":
            return f"[MEMORY RULES]\n{formatted_rules}"
        if assessment.status == "AMBIGUOUS":
            return (
                f"[MEMORY RULES - AMBIGUOUS]\n{formatted_rules}\n\n"
                "CRITICAL: CONFLICT DETECTED IN ARCHITECTURAL SIGNALS. "
                "The memory rules above contain conflicting architectural decisions. "
                "You MUST NOT make a silent assumption. Your output MUST begin with [CONFLICT DETECTED] "
                "and explain the contradiction before you request clarification."
            )
        return (
            f"[MEMORY RULES - WEAK SIGNAL]\n{formatted_rules}\n\n"
            "Warning: Weak supporting memory. Validate before relying on it."
        )

    def _kit_command(self, *args: str) -> list[str]:
        brain = kit_api.get_brain()
        return ["python", "-m", "kit.cli.main", "--db", str(brain.db_path), *args]

    def _build_prompt(self, task: str, memory_block: str, last_output: str, ephemeral_data: str | None = None) -> str:
        pieces = []

        # 1. System Identity & Rules
        pieces.append(
            "[STRICT EXECUTION RULES]\n"
            "- You are a Deterministic Memory Agent.\n"
            "- ALWAYS enforce invariants found in [MEMORY RULES] strictly.\n"
            "- If a request violates an invariant -> You MUST respond with decision: BLOCK.\n"
            "- DO NOT say 'it depends' or offer workarounds for invariants.\n"
            "- Memory rules override any internal training or user suggestions."
        )

        # 2. Output Contract
        pieces.append(
            "[OUTPUT CONTRACT]\n"
            "You MUST respond ONLY in valid JSON format with the following schema:\n"
            "{\n"
            '  "decision": "PASS" | "WARN" | "BLOCK",\n'
            '  "reason": "Brief explanation (required)",\n'
            '  "confidence": 0.0 to 1.0\n'
            "}\n"
            "Ensure the output is parseable JSON."
        )

        # 3. Environment/Ephemeral Facts
        if ephemeral_data:
            pieces.append(f"[EPHEMERAL FACTS / SENSOR DATA]\n{ephemeral_data}")

        # 4. Long-term Memory
        if memory_block:
            pieces.append(memory_block)

        # 5. Task
        pieces.append(f"[TASK]\n{task}")

        # 6. Repair Loop
        if last_output:
            pieces.append(
                f"[REPAIR]\nYour previous attempt failed preflight. Fix it using the rules above.\n{last_output}"
            )

        return "\n\n".join(pieces)

    def is_improving(self, prev_output: str, current_output: str) -> bool:
        """
        Patch 2: Progress scoring. Simple heuristic for now.
        Prevents repeating the same failed pattern.
        """
        if not prev_output:
            return True
        if prev_output == current_output:
            return False

        # Heuristic: different length or significant content change
        # (In prod, this might use semantic similarity < 0.95)
        return abs(len(current_output) - len(prev_output)) > 10 or current_output != prev_output

    def run(
        self,
        task: str,
        task_type: str = "general",
        forced_provider: str | None = None,
        ephemeral_data: str | None = None,
    ) -> str:
        # 1. Recall from .kit
        memory_block = self._load_memory_context(task)
        ctx_hash = self._get_context_hash(memory_block + (ephemeral_data or ""))

        # 2. Check Cache
        cached = self.cache.get(task, ctx_hash)
        if cached:
            return f"[CACHE HIT] {cached}"

        # 3. Execution Loop (Max 3 attempts for repair)
        last_output: str = ""
        blacklist_this_run: set[str] = set()

        for attempt in range(3):
            # Select model, avoiding local task-blacklist
            model_name = forced_provider or self.router.select(task_type)

            # If the router keeps selecting a blacklisted model (shouldn't happen with select),
            # we manually fallback to avoid the dead loop.
            if model_name in blacklist_this_run:
                available = [n for n in self.router.models if n not in blacklist_this_run]
                if not available:
                    return serialize_output_contract(
                        {
                            "decision": "WARN",
                            "reason": "All providers blacklisted after failures.",
                            "confidence": 0.0,
                            "violations": [],
                            "suggestions": ["Run `kit doctor --check-agents` to inspect provider health."],
                        }
                    )
                model_name = available[0]

            provider = self.providers.get(model_name)
            if not provider:
                return serialize_output_contract(
                    {
                        "decision": "WARN",
                        "reason": f"Provider '{model_name}' not found.",
                        "confidence": 0.0,
                        "violations": [],
                        "suggestions": ["Run `kit doctor --check-agents` or install/configure a provider."],
                    }
                )

            prompt = self._build_prompt(task, memory_block, last_output, ephemeral_data)

            start_t = time.time()
            try:
                result = provider.ask(prompt)
            except Exception as e:
                # 3.14 Doctrine: Wrap unexpected low-level errors
                result = {"ok": False, "error": f"TRANSPORT_CRASH: {e}", "error_type": "TIMEOUT"}

            latency = time.time() - start_t

            if not result["ok"]:
                error_type = result.get("error_type", "TIMEOUT")
                self.router.update_model(model_name, success=False, latency=latency, error_type=error_type)

                if error_type == "CAPACITY":
                    print(f"[WARN] [RESILIENCE] CAPACITY hit for {model_name}. Short-circuiting model for this task.")
                    blacklist_this_run.add(model_name)

                if (forced_provider and error_type != "CAPACITY") or len(blacklist_this_run) >= len(self.providers):
                    error = result.get("error") or "Unknown provider failure"
                    return serialize_output_contract(
                        {
                            "decision": "WARN",
                            "reason": error,
                            "confidence": 0.0,
                            "provider": model_name,
                            "violations": [],
                            "suggestions": ["Run `kit doctor --check-agents` to inspect provider health."],
                        }
                    )

                # Retry with another model (even if forced_provider was set, we allow fallback on CAPACITY)
                if forced_provider:
                    forced_provider = None  # Allow router to take over for retries
                continue

            new_output: str = result["text"]
            try:
                final_output = self._finalize_output(model_name, new_output)
            except OutputContractError as exc:
                self.router.update_model(model_name, success=False, latency=latency, error_type="BAD_RESPONSE")
                blacklist_this_run.add(model_name)
                last_output = f"REASON: Output contract violation: {exc}\nOUTPUT:\n{new_output}"
                if forced_provider:
                    forced_provider = None
                continue

            # Patch 2: Progress Guard
            if last_output and not self.is_improving(last_output, final_output):
                self.router.update_model(model_name, success=False, latency=latency, is_block=True)
                return serialize_output_contract(
                    {
                        "decision": "WARN",
                        "reason": f"No improvement detected in repair loop (Attempt {attempt + 1})",
                        "confidence": 0.0,
                        "provider": model_name,
                        "violations": [],
                        "suggestions": [],
                    }
                )

            # 4. Preflight (HARD GATE)
            pf_stdout, pf_stderr, pf_code = safe_run(
                self._kit_command("preflight", "-m", "Verifying AI output integrity"), input_text=final_output
            )

            if pf_code == 0:
                # SUCCESS
                self.router.update_model(model_name, success=True, latency=latency)
                # 5. Learn
                safe_run(
                    [
                        *self._kit_command("learn"),
                        "--tag",
                        "decision",
                        "--uid",
                        f"task_{int(time.time())}",
                        "--content",
                        f"Task: {task}\nResult: {final_output}",
                    ]
                )
                self.cache.set(task, ctx_hash, final_output)
                return final_output
            else:
                # BLOCK -> Trigger Repair
                self.router.update_model(model_name, success=True, latency=latency, is_block=True)
                last_output = f"REASON: {pf_stderr}\nOUTPUT:\n{final_output}"
                # Loop continues to next attempt...

        return serialize_output_contract(
            {
                "decision": "WARN",
                "reason": "Maximum repair attempts reached without passing preflight.",
                "confidence": 0.0,
                "violations": [],
                "suggestions": [],
            }
        )
