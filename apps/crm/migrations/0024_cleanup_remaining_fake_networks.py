from django.db import migrations


def cleanup_remaining_fake_networks(apps, schema_editor):
    """Идемпотентно: для тех, у кого уже применялась старая версия 0023."""
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
        ("crm", "0023_remove_auto_telecom_networks"),
    ]

    operations = [
        migrations.RunPython(cleanup_remaining_fake_networks, migrations.RunPython.noop),
    ]
