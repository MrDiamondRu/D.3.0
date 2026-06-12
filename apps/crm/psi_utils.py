from __future__ import annotations

from datetime import date

from django.utils import timezone

ACTIVE_PSI_STATUSES = {"assigned", "overdue", "in_progress"}


def partition_psis(all_psis: list) -> tuple[list, list]:
    all_psis = sorted(
        all_psis,
        key=lambda psi: (
            psi.end_date is None,
            -(psi.end_date.toordinal() if psi.end_date else date.min.toordinal()),
            -psi.pk,
        ),
    )
    visible_psis = [psi for psi in all_psis if psi.status in ACTIVE_PSI_STATUSES]
    latest_success = next((psi for psi in all_psis if psi.status == "successful"), None)
    latest_failed = next((psi for psi in all_psis if psi.status == "failed"), None)
    for candidate in (latest_success, latest_failed):
        if candidate and candidate not in visible_psis:
            visible_psis.append(candidate)
    history_psis = [psi for psi in all_psis if psi not in visible_psis]
    return visible_psis, history_psis


def annotate_psi_schedule_hints(psis: list) -> None:
    today = timezone.localdate()
    for psi in psis:
        if psi.end_date:
            delta_days = (psi.end_date - today).days
            if delta_days > 0:
                psi.schedule_hint = f"до завершения {delta_days} дн."
            elif delta_days == 0:
                psi.schedule_hint = "завершается сегодня"
            else:
                psi.schedule_hint = f"просрочено на {abs(delta_days)} дн."
        elif psi.start_date and psi.start_date > today:
            psi.schedule_hint = f"старт через {(psi.start_date - today).days} дн."
        else:
            psi.schedule_hint = "сроки не заданы"


def build_psi_history_payload(history_psis: list) -> list[dict]:
    return [
        {
            "id": psi.pk,
            "status": psi.get_status_display(),
            "status_value": psi.status,
            "responsible": str(psi.responsible) if psi.responsible_id else "—",
            "responsible_id": psi.responsible_id or "",
            "start_date": psi.start_date.strftime("%d.%m.%Y") if psi.start_date else "—",
            "start_iso": psi.start_date.isoformat() if psi.start_date else "",
            "end_date": psi.end_date.strftime("%d.%m.%Y") if psi.end_date else "—",
            "end_iso": psi.end_date.isoformat() if psi.end_date else "",
            "created_by": (
                psi.created_by.get_full_name().strip() or psi.created_by.username
                if psi.created_by_id
                else "—"
            ),
            "created_at": psi.created_at.strftime("%d.%m.%Y %H:%M") if psi.created_at else "—",
        }
        for psi in history_psis
    ]


def build_psi_busy_ranges(psis, label: str) -> list[dict]:
    ranges: list[dict] = []
    for psi in psis:
        start_date = psi.start_date or psi.end_date
        end_date = psi.end_date or psi.start_date
        if not start_date or not end_date:
            continue
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        ranges.append(
            {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "operator_name": label,
            }
        )
    return ranges
