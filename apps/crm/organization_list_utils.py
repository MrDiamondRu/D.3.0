from django.db.models import Count, OuterRef, Prefetch, Q, Subquery

from apps.crm.models import (
    EntityStatusLink,
    OrgAction,
    TelecomLicenseStatus,
    TelecomOperatorAuditEvent,
)


def status_links_prefetch() -> Prefetch:
    return Prefetch(
        "status_links",
        queryset=EntityStatusLink.objects.select_related("status"),
    )


def org_actions_prefetch() -> Prefetch:
    return Prefetch(
        "org_actions",
        queryset=OrgAction.objects.order_by("deadline", "pk"),
    )


def annotate_telecom_list(qs):
    last_audit = (
        TelecomOperatorAuditEvent.objects.filter(telecom_operator_id=OuterRef("pk"))
        .order_by("-created_at")
        .values("created_at")[:1]
    )
    return qs.annotate(
        list_active_licenses_count=Count(
            "licenses",
            filter=Q(licenses__status=TelecomLicenseStatus.ACTIVE),
        ),
        list_last_history_at=Subquery(last_audit),
    )


def annotate_ori_list(qs):
    last_action = (
        OrgAction.objects.filter(organization_id=OuterRef("pk"))
        .order_by("-updated_at")
        .values("updated_at")[:1]
    )
    return qs.annotate(list_last_history_at=Subquery(last_action))


def annotate_data_source_list(qs):
    last_action = (
        OrgAction.objects.filter(data_source_id=OuterRef("pk"))
        .order_by("-updated_at")
        .values("updated_at")[:1]
    )
    return qs.annotate(list_last_history_at=Subquery(last_action))
