# Generated manually to update inactive license label

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0012_psi_simplify_status_and_remove_protocol"),
    ]

    operations = [
        migrations.AlterField(
            model_name="telecomoperatorlicense",
            name="status",
            field=models.CharField(
                choices=[("active", "Действующая"), ("inactive", "Недействующая")],
                default="active",
                max_length=16,
                verbose_name="Статус",
            ),
        ),
    ]
