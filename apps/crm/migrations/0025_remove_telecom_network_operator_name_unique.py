from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0024_cleanup_remaining_fake_networks"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="telecomnetwork",
            name="uniq_telecom_network_operator_name",
        ),
    ]
