from django.core.management.base import BaseCommand

from apps.crm.models import (
    DocumentType,
    EventStatus,
    EventType,
    InteractionObjectType,
    InteractionStatus,
    OrganizationStatus,
    OrganizationType,
    PsiStatus,
)


def upsert_reference(model, names):
    for name in names:
        model.objects.get_or_create(name=name)


class Command(BaseCommand):
    help = "Заполняет базовые справочники CRM."

    def handle(self, *args, **options):
        upsert_reference(
            OrganizationType,
            [
                "ОРИ",
                "Организатор распространения информации",
                "Хостинг",
                "Источник ЕИАС",
                "Оператор связи",
            ],
        )
        upsert_reference(
            OrganizationStatus,
            ["Требуется действие", "Действий не требуется", "Завершено взаимодействие"],
        )
        upsert_reference(
            InteractionStatus,
            ["Передан в работу", "Пуско наладка", "Подписание документов", "В РКН", "Отмена", "Смена формата"],
        )
        upsert_reference(
            InteractionObjectType,
            ["Сайт", "Приложение", "Лицензия хостинг", "Лицензия ПД", "Лицензия ТФОП"],
        )
        upsert_reference(PsiStatus, ["Назначен", "В работе", "Успешное завершение", "Провалены", "Просрочены"])
        upsert_reference(EventType, ["Совещание", "Встреча", "Созвон"])
        upsert_reference(EventStatus, ["Запланировано", "Состоялось", "Не состоялось"])
        upsert_reference(
            DocumentType,
            ["Протокол", "Акт", "Соглашение", "Письмо", "Инструкция", "Информационная модель"],
        )
        self.stdout.write(self.style.SUCCESS("Справочники успешно заполнены."))
