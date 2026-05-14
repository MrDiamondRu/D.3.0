# Generated manually for telecom operator, licenses, and related FKs

import apps.crm.validators
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0005_remove_organization_status_organization_statuses"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LicenseOrderNumber",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True, verbose_name="Наименование")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("alias", models.CharField(blank=True, max_length=255, verbose_name="Синоним для импорта")),
            ],
            options={
                "verbose_name": "Номер приказа",
                "verbose_name_plural": "Номера приказов",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="TelecomOperator",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата изменения")),
                (
                    "icon",
                    models.ImageField(blank=True, null=True, upload_to="telecom_operators/icons/", verbose_name="Иконка"),
                ),
                ("name", models.CharField(max_length=500, verbose_name="Наименование организации")),
                (
                    "inn",
                    models.CharField(
                        db_index=True,
                        max_length=12,
                        validators=[django.core.validators.MinLengthValidator(10)],
                        verbose_name="ИНН",
                    ),
                ),
                ("case_number", models.CharField(blank=True, max_length=128, verbose_name="Номер дела")),
                (
                    "sites",
                    models.JSONField(
                        blank=True,
                        default=list,
                        validators=[apps.crm.validators.validate_url_list],
                        verbose_name="Сайты",
                    ),
                ),
                ("correspondence_address", models.TextField(blank=True, verbose_name="Адрес для корреспонденции")),
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
                    "responsible_person",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="responsible_telecom_operators",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Ответственное лицо",
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
                (
                    "statuses",
                    models.ManyToManyField(
                        blank=True,
                        related_name="telecom_operators_by_statuses",
                        to="crm.organizationstatus",
                        verbose_name="Статусы",
                    ),
                ),
            ],
            options={
                "verbose_name": "Оператор связи",
                "verbose_name_plural": "Операторы связи",
                "ordering": ("name",),
            },
        ),
        migrations.AddIndex(
            model_name="telecomoperator",
            index=models.Index(fields=["inn"], name="crm_telecom_inn_0f3e8d_idx"),
        ),
        migrations.AddIndex(
            model_name="telecomoperator",
            index=models.Index(fields=["name"], name="crm_telecom_name_8a1c2b_idx"),
        ),
        migrations.AddConstraint(
            model_name="telecomoperator",
            constraint=models.UniqueConstraint(fields=("inn", "name"), name="uniq_telecom_operator_inn_name"),
        ),
        migrations.CreateModel(
            name="TelecomOperatorLicense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата изменения")),
                ("title", models.CharField(max_length=500, verbose_name="Наименование")),
                ("number", models.CharField(blank=True, max_length=255, verbose_name="Номер")),
                ("start_date", models.DateField(blank=True, null=True, verbose_name="Начало действия")),
                ("end_date", models.DateField(blank=True, null=True, verbose_name="Окончание действия")),
                ("territory", models.TextField(blank=True, verbose_name="Территория действия")),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Действующая"), ("inactive", "Не действующая")],
                        default="active",
                        max_length=16,
                        verbose_name="Статус",
                    ),
                ),
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
                        related_name="licenses",
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
                "verbose_name": "Лицензия",
                "verbose_name_plural": "Лицензии",
                "ordering": ("telecom_operator", "start_date", "title"),
            },
        ),
        migrations.AddConstraint(
            model_name="telecomoperatorlicense",
            constraint=models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="telecom_license_dates_valid",
            ),
        ),
        migrations.CreateModel(
            name="LicenseOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата изменения")),
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
                    "license",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="orders",
                        to="crm.telecomoperatorlicense",
                        verbose_name="Лицензия",
                    ),
                ),
                (
                    "order_number",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="license_orders",
                        to="crm.licenseordernumber",
                        verbose_name="Номер приказа",
                    ),
                ),
                (
                    "orm_vendor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="license_orders",
                        to="crm.ormvendor",
                        verbose_name="Производитель ТС (ИС) ОРМ",
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
                "verbose_name": "Приказ лицензии",
                "verbose_name_plural": "Приказы лицензий",
                "ordering": ("license", "id"),
            },
        ),
        migrations.AddField(
            model_name="licenseorder",
            name="documents",
            field=models.ManyToManyField(
                blank=True,
                related_name="license_orders",
                to="crm.document",
                verbose_name="Документы",
            ),
        ),
        migrations.AddField(
            model_name="contact",
            name="telecom_operator",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="operator_contacts",
                to="crm.telecomoperator",
                verbose_name="Оператор связи",
            ),
        ),
        migrations.AlterField(
            model_name="contact",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contacts",
                to="crm.organization",
                verbose_name="Организация",
            ),
        ),
        migrations.AddField(
            model_name="comment",
            name="telecom_operator",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="operator_comments",
                to="crm.telecomoperator",
                verbose_name="Оператор связи",
            ),
        ),
        migrations.AlterField(
            model_name="comment",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="comments",
                to="crm.organization",
                verbose_name="Организация",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="telecom_operator",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="operator_documents",
                to="crm.telecomoperator",
                verbose_name="Оператор связи",
            ),
        ),
        migrations.AlterField(
            model_name="document",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to="crm.organization",
                verbose_name="Организация",
            ),
        ),
        migrations.AddField(
            model_name="psi",
            name="license_order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="psis",
                to="crm.licenseorder",
                verbose_name="Приказ лицензии",
            ),
        ),
        migrations.AddField(
            model_name="psi",
            name="telecom_operator",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="operator_psis",
                to="crm.telecomoperator",
                verbose_name="Оператор связи",
            ),
        ),
        migrations.AlterField(
            model_name="psi",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="psis",
                to="crm.organization",
                verbose_name="Организация",
            ),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(fields=["telecom_operator", "last_name"], name="crm_contact_telecom_ln_idx"),
        ),
        migrations.AddConstraint(
            model_name="contact",
            constraint=models.CheckConstraint(
                condition=models.Q(organization__isnull=False, telecom_operator__isnull=True)
                | models.Q(organization__isnull=True, telecom_operator__isnull=False),
                name="contact_org_xor_operator",
            ),
        ),
        migrations.AddConstraint(
            model_name="comment",
            constraint=models.CheckConstraint(
                condition=models.Q(organization__isnull=False, telecom_operator__isnull=True)
                | models.Q(organization__isnull=True, telecom_operator__isnull=False),
                name="comment_org_xor_operator",
            ),
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.CheckConstraint(
                condition=models.Q(organization__isnull=False, telecom_operator__isnull=True)
                | models.Q(organization__isnull=True, telecom_operator__isnull=False),
                name="document_org_xor_operator",
            ),
        ),
        migrations.AddConstraint(
            model_name="psi",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    organization__isnull=False,
                    telecom_operator__isnull=True,
                    license_order__isnull=True,
                )
                | models.Q(
                    organization__isnull=True,
                    telecom_operator__isnull=False,
                    license_order__isnull=True,
                )
                | models.Q(
                    organization__isnull=True,
                    telecom_operator__isnull=True,
                    license_order__isnull=False,
                ),
                name="psi_single_scope",
            ),
        ),
    ]
