# Generated manually for TelecomOperator audit events

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0007_remove_telecom_operator_from_document_and_psi"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TelecomOperatorAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата события")),
                (
                    "event_type",
                    models.CharField(
                        choices=[("create", "Создание"), ("update", "Изменение"), ("delete", "Удаление")],
                        max_length=16,
                        verbose_name="Тип события",
                    ),
                ),
                ("operator_name", models.CharField(blank=True, max_length=500, verbose_name="Наименование оператора")),
                (
                    "telecom_operator",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to="crm.telecomoperator",
                        verbose_name="Оператор связи",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="telecom_operator_audit_events",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Событие аудита оператора связи",
                "verbose_name_plural": "События аудита операторов связи",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="telecomoperatorauditevent",
            index=models.Index(fields=["created_at"], name="crm_telecom_created_aud_idx"),
        ),
        migrations.AddIndex(
            model_name="telecomoperatorauditevent",
            index=models.Index(fields=["event_type"], name="crm_telecom_event_aud_idx"),
        ),
    ]
