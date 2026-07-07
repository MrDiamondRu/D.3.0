# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0017_remove_interactionobjecttype"),
    ]

    operations = [
        migrations.CreateModel(
            name="EntityStatus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.CharField(max_length=500, verbose_name="Текст")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("status", "Статус"),
                            ("message", "Сообщение"),
                            ("warning", "Предупреждение"),
                        ],
                        default="status",
                        max_length=16,
                        verbose_name="Тип",
                    ),
                ),
            ],
            options={
                "verbose_name": "Статус",
                "verbose_name_plural": "Статусы",
                "ordering": ("kind", "text"),
            },
        ),
        migrations.CreateModel(
            name="EntityStatusLink",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "data_source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_links",
                        to="crm.datasource",
                        verbose_name="Источник данных",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_links",
                        to="crm.ori",
                        verbose_name="ОРИ",
                    ),
                ),
                (
                    "status",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="crm.entitystatus",
                        verbose_name="Статус",
                    ),
                ),
                (
                    "telecom_operator",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_links",
                        to="crm.telecomoperator",
                        verbose_name="Оператор связи",
                    ),
                ),
            ],
            options={
                "verbose_name": "Привязка статуса",
                "verbose_name_plural": "Привязки статусов",
                "ordering": ("status", "pk"),
            },
        ),
        migrations.AddField(
            model_name="datasource",
            name="statuses",
            field=models.ManyToManyField(
                blank=True,
                related_name="data_sources",
                through="crm.EntityStatusLink",
                through_fields=("data_source", "status"),
                to="crm.entitystatus",
                verbose_name="Статусы",
            ),
        ),
        migrations.AddField(
            model_name="ori",
            name="statuses",
            field=models.ManyToManyField(
                blank=True,
                related_name="organizations",
                through="crm.EntityStatusLink",
                through_fields=("organization", "status"),
                to="crm.entitystatus",
                verbose_name="Статусы",
            ),
        ),
        migrations.AddField(
            model_name="telecomoperator",
            name="statuses",
            field=models.ManyToManyField(
                blank=True,
                related_name="telecom_operators",
                through="crm.EntityStatusLink",
                through_fields=("telecom_operator", "status"),
                to="crm.entitystatus",
                verbose_name="Статусы",
            ),
        ),
        migrations.AddConstraint(
            model_name="entitystatuslink",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("data_source__isnull", True),
                    ("organization__isnull", False),
                    ("telecom_operator__isnull", True),
                )
                | models.Q(
                    ("data_source__isnull", True),
                    ("organization__isnull", True),
                    ("telecom_operator__isnull", False),
                )
                | models.Q(
                    ("data_source__isnull", False),
                    ("organization__isnull", True),
                    ("telecom_operator__isnull", True),
                ),
                name="entity_status_link_single_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="entitystatuslink",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", False)),
                fields=("status", "organization"),
                name="uniq_entity_status_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="entitystatuslink",
            constraint=models.UniqueConstraint(
                condition=models.Q(("telecom_operator__isnull", False)),
                fields=("status", "telecom_operator"),
                name="uniq_entity_status_telecom",
            ),
        ),
        migrations.AddConstraint(
            model_name="entitystatuslink",
            constraint=models.UniqueConstraint(
                condition=models.Q(("data_source__isnull", False)),
                fields=("status", "data_source"),
                name="uniq_entity_status_data_source",
            ),
        ),
    ]
