from django.core.management.base import BaseCommand

from apps.crm.models import (
    EventStatus,
    EventType,
)


def upsert_reference(model, names):
    for name in names:
        model.objects.get_or_create(name=name)


class Command(BaseCommand):
    help = "Заполняет базовые справочники CRM."

    def handle(self, *args, **options):
        upsert_reference(EventType, ["Совещание", "Встреча", "Созвон"])
        upsert_reference(EventStatus, ["Запланировано", "Состоялось", "Не состоялось"])
        self.stdout.write(self.style.SUCCESS("Справочники успешно заполнены."))
