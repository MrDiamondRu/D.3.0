# Generated manually to remove document-related models

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0013_alter_telecomoperatorlicense_status_label"),
    ]

    operations = [
        migrations.DeleteModel(
            name="DocumentLink",
        ),
        migrations.DeleteModel(
            name="EventDocumentTemplate",
        ),
        migrations.DeleteModel(
            name="Document",
        ),
        migrations.DeleteModel(
            name="DocumentType",
        ),
    ]
