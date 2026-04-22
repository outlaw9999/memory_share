from kit.flow.surface import (
    build_flow_suggestions,
    curate_flow_signals,
    runtime_signal_from_substrate,
)


def test_flow_signal_ordering_is_priority_driven():
    signals = [
        {"uid": "GAP:db", "confidence": "high", "source": "cognitive_core", "line": 1},
        {"uid": "STRUCTURAL:FUNCTION", "confidence": "high", "source": "vantage", "line": 2},
        {"uid": "RISK:sql.interpolation", "confidence": "high", "source": "security_lens", "line": 3},
    ]

    curated = curate_flow_signals(signals, top_k=3)

    assert [signal["uid"] for signal in curated] == [
        "RISK:sql.interpolation",
        "GAP:db",
        "STRUCTURAL:FUNCTION",
    ]


def test_flow_signal_deduplicates_structural_hash():
    signals = [
        {
            "uid": "DRIFT:STRUCTURAL",
            "confidence": "high",
            "source": "vantage",
            "line": 10,
            "structural_hash": "abc123",
        },
        {
            "uid": "STRUCTURAL:FUNCTION",
            "confidence": "high",
            "source": "vantage",
            "line": 11,
            "structural_hash": "abc123",
        },
    ]

    curated = curate_flow_signals(signals, top_k=3)

    assert len(curated) == 1
    assert curated[0]["structural_hash"] == "abc123"


def test_flow_suggestions_filter_low_confidence_and_use_fallback():
    signals = [
        {"uid": "AMBIGUITY:db", "confidence": "low", "source": "cognitive_core", "line": 4},
    ]

    curated = curate_flow_signals(signals, top_k=3)
    suggestions = build_flow_suggestions(curated, ["Consider documenting this signal"])

    assert curated == []
    assert suggestions == ["Consider documenting this signal"]


def test_runtime_signal_maps_to_repair_command():
    substrate = {
        "is_locked": False,
        "venv_discovered": "E:/repo/.venv",
        "interpreter": "C:/Python314/python.exe",
    }

    runtime_signal = runtime_signal_from_substrate(substrate)
    suggestions = build_flow_suggestions([runtime_signal] if runtime_signal else [])

    assert runtime_signal is not None
    assert runtime_signal["uid"] == "RUNTIME:INTERPRETER_MISMATCH"
    assert suggestions == ["run repair-python-venv"]
