import re
from dataclasses import dataclass
from enum import StrEnum


class RiskCategory(StrEnum):
    SQL_INJECTION = "sql.interpolation"
    AUTH_BYPASS = "auth.bypass"
    UNSAFE_FS = "fs.unsafe"


@dataclass
class RiskSignal:
    category: RiskCategory
    confidence: str
    line: int
    content: str
    evidence: str = ""


class RiskEngine:
    """
    Kit Semantic Overlay Layer: Risk Engine v0.1
    Implements behavioral pattern matching for SQL and AUTH risks.
    """

    def __init__(self):
        # Phase A: Regex Sensors
        self.sql_patterns = [
            # SQL_01-06: Standard interpolations
            (re.compile(r"(?i)(SELECT|INSERT|UPDATE|DELETE).*{.*}"), "sql.interpolation"),
            (re.compile(r"(?i)(SELECT|INSERT|UPDATE|DELETE).*\+.*"), "sql.interpolation"),
            (re.compile(r"(?i)(SELECT|INSERT|UPDATE|DELETE).*\.format\("), "sql.interpolation"),
            (re.compile(r"(?i)(SELECT|INSERT|UPDATE|DELETE).*%\s*\w+"), "sql.interpolation"),
        ]

        # Phase B: Heuristic Sensors (Detecting loops, etc)
        self.loop_pattern = re.compile(r"\b(for|while)\b")
        self.execute_pattern = re.compile(r"\.execute\(")

    def scan_code(self, code: str) -> list[RiskSignal]:
        """
        Scan a block of code for semantic risks.
        """
        signals = []
        lines = code.splitlines()

        # Contextual tracking for SQL_12 (Loops + Execute)
        in_loop = False

        for i, line in enumerate(lines):
            line_num = i + 1
            clean_line = line.strip()

            # 1. Simple Regex Hits (Phase A)
            for pattern, _category in self.sql_patterns:
                if pattern.search(clean_line):
                    signals.append(
                        RiskSignal(
                            category=RiskCategory.SQL_INJECTION,
                            confidence="high" if 'f"' in clean_line or "%" in clean_line else "medium",
                            line=line_num,
                            content=clean_line,
                            evidence=f"Pattern match: {pattern.pattern}",
                        )
                    )

            # 2. Contextual Hits (Phase B - e.g., SQL_12)
            if self.loop_pattern.search(clean_line):
                in_loop = True

            # If we see execute inside a loop, and we are in a file suspicious of SQL interpolation
            if in_loop and self.execute_pattern.search(clean_line):
                # Look back or forward for interpolation in the same block (simplified for v0.1)
                signals.append(
                    RiskSignal(
                        category=RiskCategory.SQL_INJECTION,
                        confidence="high",
                        line=line_num,
                        content=clean_line,
                        evidence="SQL_12: execute() detected inside a loop (Batch Loop Risk)",
                    )
                )

        return signals

    def scan_auth_risks(self, code: str) -> list[RiskSignal]:
        """
        Scan for Auth-related risks (AUTH_01, 02, 03).
        """
        signals = []
        lines = code.splitlines()

        # AUTH_01: Web route without auth decorator (Standard Heuristic)
        # Patterns for common web frameworks (FastAPI, Flask, etc.)
        route_pattern = re.compile(r"@\w+\.(route|get|post|put|delete|patch|patch_)\(")
        auth_pattern = re.compile(r"(auth|login_required|permission|guard|jwt|api_key|secured)")

        last_route_line = -1
        last_route_content = ""

        for i, line in enumerate(lines):
            line_num = i + 1
            clean_line = line.strip()

            if route_pattern.search(clean_line):
                last_route_line = line_num
                last_route_content = clean_line
            elif last_route_line != -1:
                # Check next 3 lines for auth decorator or function definition
                if i - last_route_line < 3:
                    if auth_pattern.search(clean_line):
                        last_route_line = -1  # Found auth
                    elif "def " in clean_line:
                        # Found function definition WITHOUT an intervening auth decorator
                        signals.append(
                            RiskSignal(
                                category=RiskCategory.AUTH_BYPASS,
                                confidence="high",
                                line=last_route_line,
                                content=last_route_content,
                                evidence="AUTH_01: Route defined without visible authentication guard",
                            )
                        )
                        last_route_line = -1

        return signals
