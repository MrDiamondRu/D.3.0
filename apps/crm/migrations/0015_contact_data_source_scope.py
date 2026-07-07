# Generated manually for Contact data_source support

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0014_add_archive_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="data_source",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contacts",
                to="crm.datasource",
                verbose_name="Источник данных",
            ),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(fields=["data_source", "first_name"], name="crm_contact_ds_fn_idx"),
        ),
        migrations.RemoveConstraint(
            model_name="contact",
            name="contact_org_xor_operator",
        ),
        migrations.AddConstraint(
            model_name="contact",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    organization__isnull=False,
                    telecom_operator__isnull=True,
                    data_source__isnull=True,
                )
                | models.Q(
                    organization__isnull=True,
                    telecom_operator__isnull=False,
                    data_source__isnull=True,
                )
                | models.Q(
                    organization__isnull=True,
                    telecom_operator__isnull=True,
                    data_source__isnull=False,
                ),
                name="contact_org_xor_operator",
            ),
        ),
    ]
