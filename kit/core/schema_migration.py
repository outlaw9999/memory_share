from typing import Any

def migrate_context(data: dict[str, Any]) -> dict[str, Any]:
    """
    Schema migration handler for execution_context payloads.
    Provides future-proofing for version leaps.
    """
    version = data.get("schema_version")

    if version == "1.0":
        return data

    raise RuntimeError(
        f"Unsupported schema version: {version}. "
        "Upgrade Toolkit or check migration policies."
    )
