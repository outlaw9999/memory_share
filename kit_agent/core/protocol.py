import time
from typing import Any, Dict

import kit.api as kit_api
from kit_agent.utils.process import safe_run
from kit_agent.core.router import ModelRouter
from kit_agent.core.cache import SemanticCache


class AMSBProtocol:
    def __init__(self, router: ModelRouter, providers: Dict[str, Any], cache: SemanticCache):
        self.router = router
        self.providers = providers
        self.cache = cache

    def _get_context_hash(self, context_text: str) -> str:
        import hashlib
        return hashlib.md5(context_text.encode()).hexdigest()

    def _decorate_output(self, model_name: str, output: str) -> str:
        if model_name == "local":
            return f"[LOCAL MODE]\n{output}"
        return output

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
                content = content[:limit-3] + "..."
                
            if content:
                lines.append(f"- {content}")
        return "\n".join(lines[:3])

    def _memory_matches_task(self, task: str, memories: list[Any]) -> bool:
        stop_words = {"what", "about", "with", "from", "into", "this", "that", "design"}
        raw_terms = [term.lower() for term in task.replace(".", " ").replace("?", " ").split() if len(term) >= 4]
        task_terms = {term for term in raw_terms if term not in stop_words}
        if not task_terms:
            return bool(memories)

        for memory in memories:
            content_lower = memory.content.lower()
            if any(
                term in content_lower
                or term.rstrip("s") in content_lower
                or (term.endswith("e") and f"{term[:-1]}ing" in content_lower)
                for term in task_terms
            ):
                return True
        return False

    def _load_memory_context(self, task: str) -> str:
        assessment = kit_api.recall_with_assessment([], limit=3, here=True, fast=True)

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
            except Exception:
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

    def _build_prompt(self, task: str, memory_block: str, last_output: str) -> str:
        prompt = f"[TASK]\n{task}"
        if memory_block:
            prompt = f"{memory_block}\n\n{prompt}"
        if last_output:
            prompt += f"\n\n[REPAIR]\nYour previous attempt failed preflight. Fix it using the memory above.\n{last_output}"
        return prompt

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

    def run(self, task: str, task_type: str = "general", forced_provider: str | None = None) -> str:
        # 1. Recall from .kit
        memory_block = self._load_memory_context(task)
        ctx_hash = self._get_context_hash(memory_block)

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
                    return f"[ABORT] All providers blacklisted after failures."
                model_name = available[0]

            provider = self.providers.get(model_name)
            if not provider:
                 return f"[ABORT] Provider '{model_name}' not found."

            prompt = self._build_prompt(task, memory_block, last_output)

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
                    return f"[FAILED:{model_name}] {error}"
                
                # Retry with another model (even if forced_provider was set, we allow fallback on CAPACITY)
                if forced_provider:
                    forced_provider = None # Allow router to take over for retries
                continue

            new_output: str = result["text"]
            
            # Patch 2: Progress Guard
            if last_output and not self.is_improving(last_output, new_output):
                self.router.update_model(model_name, success=False, latency=latency, is_block=True)
                return f"[ABORT] No improvement detected in repair loop (Attempt {attempt+1})"

            # 4. Preflight (HARD GATE)
            pf_stdout, pf_stderr, pf_code = safe_run(
                ["python", "kit.py", "preflight", "-m", "Verifying AI output integrity"],
                input_text=new_output
            )
            
            if pf_code == 0:
                # SUCCESS
                self.router.update_model(model_name, success=True, latency=latency)
                # 5. Learn
                safe_run([
                    "python", "kit.py", "learn", 
                    "--tag", "decision", 
                    "--uid", f"task_{int(time.time())}",
                    "--content", f"Task: {task}\nResult: {new_output}"
                ])
                final_output = self._decorate_output(model_name, new_output)
                self.cache.set(task, ctx_hash, final_output)
                return final_output
            else:
                # BLOCK -> Trigger Repair
                self.router.update_model(model_name, success=True, latency=latency, is_block=True)
                last_output = f"REASON: {pf_stderr}\nOUTPUT:\n{new_output}"
                # Loop continues to next attempt...

        return "[FAILED] Maximum repair attempts reached without passing preflight."
