from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from typing import Any


DATE_FILE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})\.md$", re.IGNORECASE)


def resolve_workspace_root(script_file: str) -> str:
    return os.environ.get(
        "ANTIGRAVITY_WORKSPACE_ROOT",
        os.path.abspath(os.path.join(os.path.dirname(script_file), "..", "..")),
    )


def slugify(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "unknown"


def to_posix_path(path: str) -> str:
    return os.path.normpath(path).replace("\\", "/")


def relative_path(file_path: str, workspace_root: str) -> str:
    try:
        return to_posix_path(os.path.relpath(file_path, workspace_root))
    except ValueError:
        return to_posix_path(file_path)


def split_parts(file_path: str, workspace_root: str) -> list[str]:
    return [
        part for part in relative_path(file_path, workspace_root).split("/") if part
    ]


def derive_project_name(file_path: str, workspace_root: str) -> str:
    parts = split_parts(file_path, workspace_root)
    if "projects" in parts:
        idx = parts.index("projects")
        if len(parts) > idx + 1:
            return parts[idx + 1]
    return "Root"


def derive_project_name_from_brain(brain_name: str) -> str:
    if brain_name.startswith("antigravity_"):
        slug = brain_name[len("antigravity_") :]
        if slug in {"root", "prime"}:
            return "Root"
        if slug == "global":
            return "Global"
        return slug
    return brain_name


def derive_scope(project_name: str) -> str:
    if project_name in {"Root", "Global", "unknown", "Unknown"}:
        return "workspace"
    return "project"


def derive_source_layer(file_path: str, workspace_root: str) -> str:
    for part in split_parts(file_path, workspace_root):
        if part.startswith("layer"):
            return part
    return "unknown"


def derive_source_kind(file_path: str, workspace_root: str, source_layer: str) -> str:
    parts = split_parts(file_path, workspace_root)
    if source_layer == "layer1_stream":
        return "project_stream" if "projects" in parts else "daily_log"
    if source_layer == "layer2_core":
        return "core_memory"
    if source_layer == "layer2_private":
        return "private_memory"
    return "unknown"


def derive_privacy(file_path: str, workspace_root: str, source_layer: str) -> str:
    rel_path = relative_path(file_path, workspace_root)
    if "layer2_private" in rel_path:
        return "private"
    if source_layer == "layer1_stream":
        return "restricted"
    return "shareable"


def infer_source_date(file_path: str) -> str | None:
    match = DATE_FILE_RE.search(os.path.basename(file_path))
    if match:
        return match.group("date")
    return None


def infer_source_timestamp(file_path: str) -> datetime:
    return datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC)


def extract_primary_heading(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip().lstrip("\ufeff")
        if stripped.startswith("#"):
            return stripped
    return None


def build_chunk_metadata(
    *,
    file_path: str,
    workspace_root: str,
    project_name: str,
    brain_name: str,
    chunk: dict[str, Any],
    source_timestamp: datetime | None,
) -> dict[str, Any]:
    source_layer = derive_source_layer(file_path, workspace_root)
    source_kind = derive_source_kind(file_path, workspace_root, source_layer)
    privacy = derive_privacy(file_path, workspace_root, source_layer)
    project_slug = slugify(project_name)
    scope = derive_scope(project_name)
    rel_path = relative_path(file_path, workspace_root)
    heading = chunk.get("heading") or extract_primary_heading(chunk.get("content", ""))
    content = chunk.get("content", "")

    metadata: dict[str, Any] = {
        "metadata_version": 2,
        "project": project_name,
        "project_slug": project_slug,
        "scope": scope,
        "privacy": privacy,
        "brain_name": brain_name,
        "source": os.path.normpath(file_path),
        "source_path": rel_path,
        "source_file": os.path.basename(file_path),
        "source_layer": source_layer,
        "source_kind": source_kind,
        "chunk_index": int(chunk.get("chunk_index", 0)),
        "chunk_count": int(chunk.get("chunk_count", 1)),
        "chunk_chars": len(content),
        "content_hash": hashlib.sha1(content.encode("utf-8")).hexdigest()[:16],
        "indexed_at": datetime.now(UTC).isoformat(),
    }

    if source_timestamp is not None:
        metadata["source_timestamp"] = source_timestamp.isoformat()

    source_date = infer_source_date(file_path)
    if source_date:
        metadata["source_date"] = source_date

    if heading:
        metadata["source_heading"] = heading
        metadata["source_heading_slug"] = slugify(heading)[:80]

    return metadata


def build_tags(metadata: dict[str, Any]) -> set[str]:
    tags = {
        f"project:{metadata.get('project_slug', 'unknown')}",
        f"scope:{metadata.get('scope', 'workspace')}",
        f"privacy:{metadata.get('privacy', 'shareable')}",
        f"layer:{metadata.get('source_layer', 'unknown')}",
        f"kind:{metadata.get('source_kind', 'unknown')}",
    }

    if metadata.get("source_date"):
        tags.add(f"date:{metadata['source_date']}")

    if metadata.get("source_heading_slug"):
        tags.add(f"heading:{metadata['source_heading_slug']}")

    return tags
