from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0018_entity_status"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ori",
            name="registry_record_url",
        ),
    ]
