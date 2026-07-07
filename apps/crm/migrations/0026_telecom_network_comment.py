from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0025_remove_telecom_network_operator_name_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="telecomnetwork",
            name="comment",
            field=models.TextField(blank=True, verbose_name="Комментарий"),
        ),
    ]
