# Generated manually for Contact name fields simplification

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0008_telecom_operator_audit_event"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="contact",
            name="crm_contact_organiz_5ed4e1_idx",
        ),
        migrations.RemoveIndex(
            model_name="contact",
            name="crm_contact_telecom_ln_idx",
        ),
        migrations.RemoveField(
            model_name="contact",
            name="last_name",
        ),
        migrations.RemoveField(
            model_name="contact",
            name="middle_name",
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(fields=["organization", "first_name"], name="crm_contact_org_fn_idx"),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(fields=["telecom_operator", "first_name"], name="crm_contact_tel_fn_idx"),
        ),
    ]
