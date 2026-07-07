# Generated manually

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0020_app_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TelecomNetwork",
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
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата изменения")),
                ("name", models.CharField(max_length=500, verbose_name="Наименование")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кто создал",
                    ),
                ),
                (
                    "telecom_operator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="networks",
                        to="crm.telecomoperator",
                        verbose_name="Оператор связи",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кто изменил",
                    ),
                ),
            ],
            options={
                "verbose_name": "Сеть связи",
                "verbose_name_plural": "Сети связи",
                "ordering": ("telecom_operator", "name"),
            },
        ),
        migrations.AddConstraint(
            model_name="telecomnetwork",
            constraint=models.UniqueConstraint(
                fields=("telecom_operator", "name"),
                name="uniq_telecom_network_operator_name",
            ),
        ),
        migrations.AddField(
            model_name="telecomoperatorlicense",
            name="telecom_network",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="licenses",
                to="crm.telecomnetwork",
                verbose_name="Сеть связи",
            ),
        ),
        migrations.AddField(
            model_name="licenseorder",
            name="telecom_network",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="orders",
                to="crm.telecomnetwork",
                verbose_name="Сеть связи",
            ),
        ),
        migrations.RemoveField(
            model_name="licenseorder",
            name="license",
        ),
        migrations.AlterModelOptions(
            name="licenseorder",
            options={
                "ordering": ("telecom_network", "pk"),
                "verbose_name": "Приказ лицензии",
                "verbose_name_plural": "Приказы лицензий",
            },
        ),
        migrations.AlterField(
            model_name="licenseorder",
            name="telecom_network",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="orders",
                to="crm.telecomnetwork",
                verbose_name="Сеть связи",
            ),
        ),
    ]
