from __future__ import annotations

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from apps.crm.current_user import get_current_user
from apps.crm.models import TelecomOperator, TelecomOperatorAuditEvent, TelecomOperatorAuditEventType


def _safe_user():
    user = get_current_user()
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user


@receiver(post_save, sender=TelecomOperator)
def telecom_operator_post_save(sender, instance, created, **kwargs):
    TelecomOperatorAuditEvent.objects.create(
        user=_safe_user(),
        event_type=TelecomOperatorAuditEventType.CREATE if created else TelecomOperatorAuditEventType.UPDATE,
        telecom_operator=instance,
        operator_name=instance.name,
    )


@receiver(pre_delete, sender=TelecomOperator)
def telecom_operator_pre_delete(sender, instance, **kwargs):
    TelecomOperatorAuditEvent.objects.create(
        user=_safe_user(),
        event_type=TelecomOperatorAuditEventType.DELETE,
        telecom_operator=instance,
        operator_name=instance.name,
    )
