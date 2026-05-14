# Remove Document/Psi link to TelecomOperator; PSI only via LicenseOrder or Organization

import django.db.models.deletion
from django.db import migrations, models


def delete_operator_only_documents(apps, schema_editor):
    Document = apps.get_model("crm", "Document")
    Document.objects.filter(organization_id__isnull=True).delete()


def delete_operator_only_psi(apps, schema_editor):
    Psi = apps.get_model("crm", "Psi")
    Psi.objects.filter(organization_id__isnull=True, license_order_id__isnull=True).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0006_telecom_operator_and_licenses"),
    ]

    operations = [
        migrations.RunPython(delete_operator_only_documents, noop_reverse),
        migrations.RunPython(delete_operator_only_psi, noop_reverse),
        migrations.RemoveConstraint(
            model_name="document",
            name="document_org_xor_operator",
        ),
        migrations.RemoveConstraint(
            model_name="psi",
            name="psi_single_scope",
        ),
        migrations.RemoveField(
            model_name="document",
            name="telecom_operator",
        ),
        migrations.RemoveField(
            model_name="psi",
            name="telecom_operator",
        ),
        migrations.AlterField(
            model_name="document",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to="crm.organization",
                verbose_name="Организация",
            ),
        ),
        migrations.AddConstraint(
            model_name="psi",
            constraint=models.CheckConstraint(
                condition=models.Q(organization__isnull=False, license_order__isnull=True)
                | models.Q(organization__isnull=True, license_order__isnull=False),
                name="psi_single_scope",
            ),
        ),
    ]
