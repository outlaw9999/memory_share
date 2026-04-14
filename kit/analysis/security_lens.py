from pathlib import Path

from kit.analysis.risk_engine import RiskEngine
from kit.models.signal import Signal


def apply_security_lens(file_path: Path, structural_signals: list[Signal]) -> list[Signal]:
    """
    Bridges Vantage's physical anchors with Kit's semantic risk signals.
    Architecture: Identity (Vantage) -> Risk (Kit).
    """
    if not file_path.exists():
        return []

    with open(file_path, encoding="utf-8", errors="replace") as f:
        code = f.read()

    engine = RiskEngine()
    semantic_risks = engine.scan_code(code)
    semantic_risks.extend(engine.scan_auth_risks(code))

    final_signals = []

    # Map each semantic risk to the closest structural anchor from Vantage
    for risk in semantic_risks:
        # Find the best anchor: closest encompassing scope
        best_anchor = None
        closest_dist = float('inf')

        for struct in structural_signals:
            # Note: Structural signals (Vantage) currently might not have line numbers
            # for all nodes, but they have Symbol IDs (UUIDs).
            # v1.2.4: We use the context provided by Vantage to find the parent symbol.

            # Simple heuristic for v0.1: match to the file-level or nearest structural hit
            # if line number information is available.
            if struct.line > 0 and struct.line <= risk.line:
                dist = risk.line - struct.line
                if dist < closest_dist:
                    closest_dist = dist
                    best_anchor = struct

        final_signals.append(
            Signal(
                uid=f"RISK:{risk.category}",
                confidence=risk.confidence,
                line=risk.line,
                source="security_lens",
                evidence=risk.evidence,
                symbol=best_anchor.symbol if best_anchor else None,
                structural_hash=best_anchor.structural_hash if best_anchor else None
            )
        )

    return final_signals
