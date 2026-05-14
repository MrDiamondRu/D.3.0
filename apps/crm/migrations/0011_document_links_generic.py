# Generated manually for generic document links

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forward_fill_document_links(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Document = apps.get_model("crm", "Document")
    DocumentLink = apps.get_model("crm", "DocumentLink")
    LicenseOrder = apps.get_model("crm", "LicenseOrder")

    organization_ct = ContentType.objects.get(app_label="crm", model="organization")
    license_order_ct = ContentType.objects.get(app_label="crm", model="licenseorder")

    rows = []
    for document in Document.objects.exclude(organization_id__isnull=True).only("id", "organization_id"):
        rows.append(
            DocumentLink(
                document_id=document.id,
                content_type_id=organization_ct.id,
                object_id=document.organization_id,
            )
        )

    through_model = LicenseOrder.documents.through
    for license_order_id, document_id in through_model.objects.all().values_list("licenseorder_id", "document_id"):
        rows.append(
            DocumentLink(
                document_id=document_id,
                content_type_id=license_order_ct.id,
                object_id=license_order_id,
            )
        )

    if rows:
        DocumentLink.objects.bulk_create(rows, ignore_conflicts=True)


def reverse_fill_document_links(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Document = apps.get_model("crm", "Document")
    DocumentLink = apps.get_model("crm", "DocumentLink")
    LicenseOrder = apps.get_model("crm", "LicenseOrder")

    organization_ct = ContentType.objects.get(app_label="crm", model="organization")
    license_order_ct = ContentType.objects.get(app_label="crm", model="licenseorder")

    for document_id, organization_id in (
        DocumentLink.objects.filter(content_type_id=organization_ct.id)
        .order_by("id")
        .values_list("document_id", "object_id")
    ):
        Document.objects.filter(id=document_id, organization_id__isnull=True).update(organization_id=organization_id)

    through_model = LicenseOrder.documents.through
    rows = [
        through_model(licenseorder_id=order_id, document_id=document_id)
        for document_id, order_id in (
            DocumentLink.objects.filter(content_type_id=license_order_ct.id)
            .values_list("document_id", "object_id")
        )
    ]
    if rows:
        through_model.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("crm", "0010_simplify_document_model"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата изменения")),
                ("object_id", models.PositiveBigIntegerField(verbose_name="ID сущности")),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crm_document_links",
                        to="contenttypes.contenttype",
                        verbose_name="Тип сущности",
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
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="crm.document",
                        verbose_name="Документ",
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
                "verbose_name": "Связь документа",
                "verbose_name_plural": "Связи документов",
            },
        ),
        migrations.AddConstraint(
            model_name="documentlink",
            constraint=models.UniqueConstraint(
                fields=("document", "content_type", "object_id"),
                name="uniq_document_link_target",
            ),
        ),
        migrations.AddIndex(
            model_name="documentlink",
            index=models.Index(fields=["content_type", "object_id"], name="crm_doclink_target_idx"),
        ),
        migrations.AddIndex(
            model_name="documentlink",
            index=models.Index(fields=["document"], name="crm_doclink_document_idx"),
        ),
        migrations.RunPython(forward_fill_document_links, reverse_fill_document_links),
        migrations.RemoveField(
            model_name="document",
            name="organization",
        ),
        migrations.RemoveField(
            model_name="licenseorder",
            name="documents",
        ),
    ]
