from __future__ import annotations

import math

from apps.crm.models import OrgAction, OrgActionStatus

_DONUT_CX = 21.0
_DONUT_CY = 21.0
_DONUT_R = 15.91549430918954
_DONUT_GAP_DEG = 2.0

ORG_ACTION_STATUS_COLORS = {
    OrgActionStatus.PLANNED.value: "#e8b339",
    OrgActionStatus.OVERDUE.value: "#d94f7a",
    OrgActionStatus.DONE.value: "#3db9b0",
}


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


def _donut_point(angle_deg: float) -> tuple[float, float]:
    """Точка на окружности; 0° — сверху, обход по часовой стрелке."""
    rad = math.radians(angle_deg - 90.0)
    return (
        _DONUT_CX + _DONUT_R * math.cos(rad),
        _DONUT_CY + _DONUT_R * math.sin(rad),
    )


def _donut_arc_path(start_deg: float, end_deg: float) -> str:
    x1, y1 = _donut_point(start_deg)
    x2, y2 = _donut_point(end_deg)
    sweep = end_deg - start_deg
    large_arc = 1 if sweep > 180.0 else 0
    return f"M {x1:.4f} {y1:.4f} A {_DONUT_R} {_DONUT_R} 0 {large_arc} 1 {x2:.4f} {y2:.4f}"


def org_action_donut_data(actions) -> dict:
    """
    Сегменты кольцевой диаграммы: по одной дуге на действие в порядке списка.
    Доля каждого сектора = 100% / N; цвет — по статусу действия.
    """
    items = list(actions)
    total = len(items)
    if not total:
        return {
            "segments": [],
            "total": 0,
            "done": 0,
            "planned": 0,
            "overdue": 0,
        }

    gap_deg = _DONUT_GAP_DEG if total > 1 else 0.0
    slice_deg = (360.0 - gap_deg * total) / total
    segments: list[dict] = []
    cursor = 0.0

    for action in items:
        status = action.status
        start_deg = cursor
        end_deg = cursor + slice_deg
        segments.append(
            {
                "status": status,
                "color": ORG_ACTION_STATUS_COLORS.get(
                    status, ORG_ACTION_STATUS_COLORS[OrgActionStatus.PLANNED.value]
                ),
                "path": _donut_arc_path(start_deg, end_deg),
                "task": action.task,
                "deadline": action.deadline,
            }
        )
        cursor = end_deg + gap_deg

    return {
        "segments": segments,
        "total": total,
        "done": sum(1 for item in items if item.status == OrgActionStatus.DONE.value),
        "planned": sum(1 for item in items if item.status == OrgActionStatus.PLANNED.value),
        "overdue": sum(1 for item in items if item.status == OrgActionStatus.OVERDUE.value),
    }
