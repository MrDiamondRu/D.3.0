# Generated manually for archive flags

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0003_actiontemplate"),
    ]

    operations = [
        migrations.AddField(
            model_name="ori",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="Архив"),
        ),
        migrations.AddField(
            model_name="datasource",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="Архив"),
        ),
        migrations.AddField(
            model_name="telecomoperator",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="Архив"),
        ),
    ]
