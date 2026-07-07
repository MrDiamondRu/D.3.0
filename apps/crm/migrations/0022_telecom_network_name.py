import django.db.models.deletion
from django.db import migrations, models


def link_network_names(apps, schema_editor):
    TelecomNetwork = apps.get_model("crm", "TelecomNetwork")
    TelecomNetworkName = apps.get_model("crm", "TelecomNetworkName")

    for network in TelecomNetwork.objects.all().iterator():
        label = (network.name_text or "").strip()
        if not label:
            continue
        ref, _ = TelecomNetworkName.objects.get_or_create(name=label)
        network.name_id = ref.pk
        network.save(update_fields=["name_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0021_telecom_network"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelecomNetworkName",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, unique=True, verbose_name="Наименование")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("alias", models.CharField(blank=True, max_length=255, verbose_name="Синоним для импорта")),
            ],
            options={
                "verbose_name": "Наименование сети связи",
                "verbose_name_plural": "Наименования сетей связи",
                "ordering": ("name",),
                "abstract": False,
            },
        ),
        migrations.RemoveConstraint(
            model_name="telecomnetwork",
            name="uniq_telecom_network_operator_name",
        ),
        migrations.RenameField(
            model_name="telecomnetwork",
            old_name="name",
            new_name="name_text",
        ),
        migrations.AddField(
            model_name="telecomnetwork",
            name="name",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="networks",
                to="crm.telecomnetworkname",
                verbose_name="Наименование",
            ),
        ),
        migrations.RunPython(link_network_names, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="telecomnetwork",
            name="name_text",
        ),
        migrations.AlterField(
            model_name="telecomnetwork",
            name="name",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="networks",
                to="crm.telecomnetworkname",
                verbose_name="Наименование",
            ),
        ),
        migrations.AddConstraint(
            model_name="telecomnetwork",
            constraint=models.UniqueConstraint(
                fields=("telecom_operator", "name"),
                name="uniq_telecom_network_operator_name",
            ),
        ),
        migrations.AlterModelOptions(
            name="telecomnetwork",
            options={
                "ordering": ("telecom_operator", "name__name"),
                "verbose_name": "Сеть связи",
                "verbose_name_plural": "Сети связи",
            },
        ),
    ]
