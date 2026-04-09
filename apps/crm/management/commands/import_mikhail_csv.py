import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction

from apps.crm.models import (
    Industry,
    InteractionObject,
    InteractionObjectType,
    InteractionStatus,
    Organization,
    OrganizationStatus,
    OrganizationType,
    OrmVendor,
)


class Command(BaseCommand):
    help = "Импортирует организации из выгрузки template/Михаил.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="template/Михаил.csv",
            help="Путь к CSV файлу с организациями",
        )

    def _get_ref(self, model, value: str):
        value = (value or "").strip()
        if not value:
            return None
        obj, _ = model.objects.get_or_create(name=value)
        return obj

    def _parse_sites(self, raw: str) -> list[str]:
        url_validator = URLValidator(schemes=["http", "https"])
        parsed_sites = []
        for chunk in [x.strip() for x in raw.split(",") if x.strip()]:
            if "приложение" in chunk.lower():
                continue
            candidate = chunk if "://" in chunk else f"https://{chunk}"
            try:
                url_validator(candidate)
            except Exception:
                continue
            parsed_sites.append(candidate)
        return parsed_sites

    def _get_or_create_user(self, raw_value: str):
        value = (raw_value or "").strip()
        if not value:
            return None
        User = get_user_model()
        user, created = User.objects.get_or_create(username=value, defaults={"is_active": True})
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = Path(options["path"])
        if not file_path.exists():
            raise CommandError(f"Файл не найден: {file_path}")

        site_type, _ = InteractionObjectType.objects.get_or_create(name="Сайт")
        app_type, _ = InteractionObjectType.objects.get_or_create(name="Приложение")

        created = 0
        updated = 0
        issues = 0
        sorm_owner_links = []

        with file_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for idx, row in enumerate(reader, start=2):
                name = (row.get("Организация") or "").strip()
                inn = (row.get("ИНН") or "").strip()
                if not name or not inn:
                    issues += 1
                    self.stdout.write(self.style.WARNING(f"Строка {idx}: пропущена, нет названия или ИНН"))
                    continue

                defaults = {
                    "responsible_person": self._get_or_create_user(row.get("Ответственное лицо") or ""),
                    "case_number": (row.get("№ дела") or "").strip(),
                    "sites": self._parse_sites((row.get("Сайт") or "").strip()),
                    "organization_type": self._get_ref(OrganizationType, row.get("Тип") or "") or OrganizationType.objects.get_or_create(name="Не указан")[0],
                    "interaction_status": self._get_ref(InteractionStatus, row.get("Статус взаимодействия") or ""),
                    "status": self._get_ref(OrganizationStatus, row.get("Статус") or ""),
                    "industry": self._get_ref(Industry, row.get("Отрасль") or ""),
                    "orm_vendor": self._get_ref(OrmVendor, row.get("Производитель ТС ОРМ") or ""),
                }

                obj, was_created = Organization.objects.update_or_create(inn=inn, name=name, defaults=defaults)
                created += int(was_created)
                updated += int(not was_created)
                sorm_owner_links.append((obj.pk, (row.get("Владелец СОРМ") or "").strip()))

                # В CSV несколько сайтов и мобильные приложения хранятся в одной строке.
                sites_raw = (row.get("Сайт") or "").strip()
                if sites_raw:
                    for chunk in [x.strip() for x in sites_raw.split(",") if x.strip()]:
                        obj_type = app_type if "приложение" in chunk.lower() else site_type
                        InteractionObject.objects.get_or_create(
                            organization=obj,
                            object_type=obj_type,
                            object_value=chunk,
                            defaults={"object_url": ""},
                        )

        for org_id, owner_name in sorm_owner_links:
            if not owner_name:
                continue
            owner = Organization.objects.filter(name=owner_name).first()
            if owner is None:
                continue
            Organization.objects.filter(pk=org_id).update(sorm_owner=owner)

        self.stdout.write(self.style.SUCCESS(f"Импорт завершен. Создано: {created}, обновлено: {updated}, проблем: {issues}."))
