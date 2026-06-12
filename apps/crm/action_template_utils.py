from __future__ import annotations

from apps.crm.models import OrgAction


def normalize_action_template_items(raw_items) -> list[dict[str, str]]:
    if not isinstance(raw_items, list):
        return []
    normalized: list[dict[str, str]] = []
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        task = str(entry.get("task", "")).strip()
        if not task:
            continue
        normalized.append(
            {
                "task": task[:500],
                "comment": str(entry.get("comment", "")).strip(),
            }
        )
    return normalized


def action_template_items_from_actions(actions: list[OrgAction]) -> list[dict[str, str]]:
    return normalize_action_template_items(
        [{"task": action.task, "comment": action.comment or ""} for action in actions]
    )
