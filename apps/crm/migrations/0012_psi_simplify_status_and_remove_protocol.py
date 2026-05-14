# Generated manually for PSI status simplification

from django.db import migrations, models


def forward_fill_psi_status(apps, schema_editor):
    Psi = apps.get_model("crm", "Psi")
    PsiStatus = apps.get_model("crm", "PsiStatus")

    mapping = {
        "назначен": "assigned",
        "назначены": "assigned",
        "в работе": "in_progress",
        "провалены": "failed",
        "просрочены": "overdue",
        "успешное завершение": "successful",
        "успешны": "successful",
    }

    statuses = {row.id: mapping.get((row.name or "").strip().lower(), "assigned") for row in PsiStatus.objects.all()}
    for psi in Psi.objects.all().only("id", "status_id"):
        Psi.objects.filter(id=psi.id).update(status_text=statuses.get(psi.status_id, "assigned"))


def reverse_fill_psi_status(apps, schema_editor):
    Psi = apps.get_model("crm", "Psi")
    PsiStatus = apps.get_model("crm", "PsiStatus")

    reverse_mapping = {
        "assigned": "Назначены",
        "in_progress": "В работе",
        "failed": "Провалены",
        "overdue": "Просрочены",
        "successful": "Успешны",
    }

    status_by_name = {s.name: s.id for s in PsiStatus.objects.all()}
    for code, name in reverse_mapping.items():
        if name not in status_by_name:
            row = PsiStatus.objects.create(name=name)
            status_by_name[name] = row.id
        Psi.objects.filter(status_text=code).update(status_id=status_by_name[name])


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0011_document_links_generic"),
    ]

    operations = [
        migrations.AddField(
            model_name="psi",
            name="status_text",
            field=models.CharField(
                choices=[
                    ("assigned", "Назначены"),
                    ("in_progress", "В работе"),
                    ("failed", "Провалены"),
                    ("overdue", "Просрочены"),
                    ("successful", "Успешны"),
                ],
                default="assigned",
                max_length=24,
                verbose_name="Статус",
            ),
        ),
        migrations.RunPython(forward_fill_psi_status, reverse_fill_psi_status),
        migrations.RemoveField(
            model_name="psi",
            name="status",
        ),
        migrations.RenameField(
            model_name="psi",
            old_name="status_text",
            new_name="status",
        ),
        migrations.RemoveField(
            model_name="psi",
            name="protocol_html_url",
        ),
        migrations.DeleteModel(
            name="PsiStatus",
        ),
    ]
