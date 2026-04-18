import subprocess
from pathlib import Path
from typing import Any

from kit.core.file_system import EncodingError, read_text_safe
from kit.core.kit_platform import GIT_TIMEOUT

FLOW_PREFIX_PRIORITY = {
    "RUNTIME:": 100,
    "RISK:": 90,
    "VIOLATION:": 80,
    "DRIFT:": 70,
    "GAP:": 60,
    "AMBIGUITY:": 50,
    "STRUCTURAL:": 40,
}
FLOW_SEVERITY_WEIGHT = {
    "high": 30,
    "medium": 20,
    "low": 10,
}
FLOW_EXACT_ACTIONS = {
    "RUNTIME:INTERPRETER_MISMATCH": "run repair-python-venv",
}
FLOW_PREFIX_ACTIONS = {
    "RISK:": "run scan",
    "VIOLATION:": "run compile",
    "DRIFT:": "run compile",
    "GAP:": "run scan",
    "STRUCTURAL:": "run scan",
}
FLOW_CONFIDENCE_VALUE = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
}
FLOW_REFLECT_SUFFIXES = {".py", ".rs", ".js", ".ts", ".go", ".rb"}
FLOW_MIN_CONFIDENCE = 0.7
FLOW_TOP_K = 2


def normalize_signal(signal: Any) -> dict[str, Any]:
    if isinstance(signal, dict):
        return signal

    if isinstance(signal, (list, tuple)):
        return {
            "uid": signal[0] if len(signal) > 0 else None,
            "source": signal[1] if len(signal) > 1 else None,
            "line": signal[2] if len(signal) > 2 else 0,
            "tag": signal[3] if len(signal) > 3 else None,
        }

    return {
        "uid": str(signal),
        "source": "unknown",
        "line": 0,
        "tag": None,
    }


def signal_confidence_value(raw_confidence: Any) -> float:
    if isinstance(raw_confidence, (int, float)):
        return max(0.0, min(float(raw_confidence), 1.0))
    if isinstance(raw_confidence, str):
        return FLOW_CONFIDENCE_VALUE.get(raw_confidence.lower(), 0.0)
    return 0.0


def signal_priority(uid: str) -> int:
    for prefix, score in FLOW_PREFIX_PRIORITY.items():
        if uid.startswith(prefix):
            return score
    return 10


def flow_sort_key(signal: dict[str, Any]) -> tuple[int, int, int, str, str, str]:
    uid = str(signal.get("uid", ""))
    severity = str(signal.get("severity", ""))
    confidence_score = int(signal_confidence_value(signal.get("confidence")) * 10)
    severity_score = FLOW_SEVERITY_WEIGHT.get(severity.lower(), 0)
    return (
        -signal_priority(uid),
        -severity_score,
        -confidence_score,
        uid,
        str(signal.get("structural_hash") or ""),
        str(signal.get("source") or ""),
    )


def curate_flow_signals(raw_signals: list[Any], top_k: int = FLOW_TOP_K) -> list[dict[str, Any]]:
    normalized = [normalize_signal(signal) for signal in raw_signals]
    filtered = [signal for signal in normalized if signal_confidence_value(signal.get("confidence")) >= FLOW_MIN_CONFIDENCE]
    ordered = sorted(filtered, key=flow_sort_key)

    curated: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    seen_fingerprints: set[tuple[str, str, int]] = set()

    for signal in ordered:
        structural_hash = signal.get("structural_hash")
        if structural_hash:
            structural_hash = str(structural_hash)
            if structural_hash in seen_hashes:
                continue
            seen_hashes.add(structural_hash)

        fingerprint = (
            str(signal.get("uid", "")),
            str(signal.get("source", "")),
            int(signal.get("line", 0) or 0),
        )
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        curated.append(signal)
        if len(curated) >= top_k:
            break

    return curated


def runtime_signal_from_substrate(substrate: dict[str, Any], error: Exception | None = None) -> dict[str, Any] | None:
    evidence: str | None = None
    uid: str | None = None

    if error and "interpreter mismatch" in str(error).lower():
        uid = "RUNTIME:INTERPRETER_MISMATCH"
        evidence = str(error)
    elif not substrate.get("is_locked", True):
        uid = "RUNTIME:INTERPRETER_MISMATCH"
        evidence = (
            "[RUNTIME LOCK] Interpreter mismatch (v1.2.4)\n"
            f"Expected: {substrate.get('venv_discovered', 'missing')}\n"
            f"Actual:   {substrate.get('interpreter', 'unknown')}"
        )

    if not uid:
        return None

    return {
        "uid": uid,
        "confidence": "high",
        "severity": "high",
        "line": 0,
        "source": "runtime_shield",
        "evidence": evidence,
    }


def flow_decision_kernel(input_text: str, brain=None) -> dict[str, Any]:
    """
    Flow Decision Micro-Kernel (v1.2.4 FINAL)
    
    input -> reflect -> signals -> suggestions -> shaped decision
    
    This closes the cognitive loop:
    - Pre-reflection: detect risk/gap/drift before execution
    - Signal shaping: convert issues to actionable suggestions
    - Decision dispatch: return shaped commands
    """
    from kit.core.kit_reflect import run_reflect
    from kit.api import get_brain
    
    try:
        brain = brain or get_brain()
        
        # Phase 1: Pre-reflection (detect signals before execution)
        if len(input_text) > 3:
            report = run_reflect(brain, input_text, scope="working")
            signals = report.signals if hasattr(report, 'signals') else []
        else:
            signals = []
        
        # Phase 2: Signal shaping
        suggestions = build_flow_suggestions(signals) if signals else []
        
        # Phase 3: Decision shaping
        return {
            "signals": signals,
            "suggestions": suggestions[:FLOW_TOP_K],
            "signal_count": len(signals),
            "ready": len(suggestions) > 0
        }
    except Exception as e:
        return {"signals": [], "suggestions": [], "signal_count": 0, "ready": False, "error": str(e)}


def map_flow_action(uid: str) -> str | None:
    exact_match = FLOW_EXACT_ACTIONS.get(uid)
    if exact_match:
        return exact_match

    for prefix, action in FLOW_PREFIX_ACTIONS.items():
        if uid.startswith(prefix):
            return action

    return None


def build_flow_suggestions(
    curated_signals: list[dict[str, Any]],
    fallback_suggestions: list[str] | None = None,
    top_k: int = FLOW_TOP_K,
) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()

    for signal in curated_signals:
        uid = str(signal.get("uid", ""))
        action = map_flow_action(uid)
        if not action or action in seen:
            continue
        seen.add(action)
        commands.append(action)
        if len(commands) >= top_k:
            return commands

    for suggestion in fallback_suggestions or []:
        suggestion = str(suggestion).strip()
        if not suggestion or suggestion in seen:
            continue
        seen.add(suggestion)
        commands.append(suggestion)
        if len(commands) >= top_k:
            break

    return commands


def build_flow_reflect_payload() -> tuple[str, Path | None]:
    changed_files: list[str] = []

    for git_cmd in (["git", "diff", "--cached", "--name-only"], ["git", "diff", "HEAD", "--name-only"]):
        try:
            result = subprocess.run(
                git_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_TIMEOUT,
                cwd=Path.cwd(),
            )
        except Exception:
            continue

        if result.returncode != 0 or not result.stdout:
            continue

        changed_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if changed_files:
            break

    pseudo_diff_lines: list[str] = []
    main_file_path: Path | None = None

    for file_name in changed_files:
        path = Path(file_name)
        if path.suffix.lower() not in FLOW_REFLECT_SUFFIXES or not path.exists():
            continue

        if main_file_path is None:
            main_file_path = path

        try:
            file_content = read_text_safe(path)
        except EncodingError:
            continue
        except Exception:
            continue

        for line in file_content.text.splitlines()[:200]:
            pseudo_diff_lines.append(f"+ {line}")

        if len(pseudo_diff_lines) >= 600:
            break

    return "\n".join(pseudo_diff_lines), main_file_path
