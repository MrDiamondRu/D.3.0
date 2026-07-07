import django.db.models.deletion
from django.db import migrations, models


def remove_fake_telecom_networks(apps, schema_editor):
    """
    Лицензии и приказы не удаляются.
    Приказы сохраняются на операторе связи, сети связи удаляются целиком.
    """
    TelecomOperatorLicense = apps.get_model("crm", "TelecomOperatorLicense")
    TelecomNetwork = apps.get_model("crm", "TelecomNetwork")
    LicenseOrder = apps.get_model("crm", "LicenseOrder")

    for order in (
        LicenseOrder.objects.select_related("telecom_network")
        .filter(telecom_network__isnull=False)
        .order_by("pk")
    ):
        order.telecom_operator_id = order.telecom_network.telecom_operator_id
        order.save(update_fields=["telecom_operator_id"])

    TelecomOperatorLicense.objects.update(telecom_network_id=None)
    LicenseOrder.objects.update(telecom_network_id=None)
    TelecomNetwork.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0022_telecom_network_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="licenseorder",
            name="telecom_operator",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="license_orders",
                to="crm.telecomoperator",
                verbose_name="Оператор связи",
            ),
        ),
        migrations.AlterField(
            model_name="licenseorder",
            name="telecom_network",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="orders",
                to="crm.telecomnetwork",
                verbose_name="Сеть связи",
            ),
        ),
        migrations.AlterModelOptions(
            name="licenseorder",
            options={
                "ordering": ("telecom_network", "pk"),
                "verbose_name": "Приказ лицензии",
                "verbose_name_plural": "Приказы лицензий",
            },
        ),
        migrations.RunPython(remove_fake_telecom_networks, migrations.RunPython.noop),
    ]
