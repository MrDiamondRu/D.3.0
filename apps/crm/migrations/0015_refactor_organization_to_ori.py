# Generated manually for ORI refactor and organization-type removal

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0014_remove_document_models"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Organization",
            new_name="Ori",
        ),
        migrations.RemoveField(
            model_name="ori",
            name="organization_type",
        ),
        migrations.DeleteModel(
            name="OrganizationType",
        ),
        migrations.AlterModelOptions(
            name="ori",
            options={
                "verbose_name": "ОРИ",
                "verbose_name_plural": "ОРИ",
                "ordering": ("name",),
            },
        ),
    ]
