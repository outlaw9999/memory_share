import logging
from typing import Any

import yaml

from kit.api import get_brain

logger = logging.getLogger("kit.skills.matcher")


def list_procedural_skills() -> list[dict[str, Any]]:
    """
    Retrieve all compiled YAML skills from Local and Global brains.
    """
    brain = get_brain()
    skills = []

    # Query observations with layer='procedural'
    # We use direct SQL for deterministic retrieval of all L3 skills
    sql = "SELECT content FROM observations WHERE layer = 'procedural' AND is_active = 1"

    # Check Local
    try:
        with brain.get_connection() as conn:
            rows = conn.execute(sql).fetchall()
            for row in rows:
                try:
                    data = yaml.safe_load(row["content"])
                    if isinstance(data, dict):
                        skills.append(data)
                except Exception as e:
                    logger.warning(f"Failed to parse local skill YAML: {e}")
    except Exception as e:
        logger.error(f"Failed to query local skills: {e}")

    # Check Global
    if brain.global_db_path and brain.global_db_path.exists():
        try:
            with brain.get_connection(brain.global_db_path) as gconn:
                rows = gconn.execute(sql).fetchall()
                for row in rows:
                    try:
                        data = yaml.safe_load(row["content"])
                        if isinstance(data, dict):
                            skills.append(data)
                    except Exception as e:
                        logger.warning(f"Failed to parse global skill YAML: {e}")
        except Exception as e:
            logger.error(f"Failed to query global skills: {e}")

    return skills


def match_trigger(message: str) -> list[dict[str, Any]]:
    """
    Match input message against skill triggers using simple keyword matching.
    Rule: Keyword must be present in message (case-insensitive).
    """
    if not message:
        return []

    message_lower = message.lower()
    all_skills = list_procedural_skills()
    matches = []

    # v0.1: Simple Keyword Match
    for skill in all_skills:
        triggers = skill.get("triggers", [])
        for trigger in triggers:
            if str(trigger).lower() in message_lower:
                matches.append(skill)
                break  # Move to next skill

    return matches
