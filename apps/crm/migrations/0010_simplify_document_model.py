# Generated manually for Document model simplification

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0009_remove_contact_last_name_middle_name"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="document",
            name="added_by",
        ),
        migrations.RemoveField(
            model_name="document",
            name="comment",
        ),
        migrations.RemoveField(
            model_name="document",
            name="html_url",
        ),
        migrations.RemoveField(
            model_name="document",
            name="title",
        ),
    ]
