import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction

from apps.crm.models import (
    DataSource,
    Industry,
    Ori,
    OrmVendor,
)

EIAS_TYPE = "Источник ЕИАС"


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

    def _is_eias_source(self, row: dict) -> bool:
        return (row.get("Тип") or "").strip() == EIAS_TYPE

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = Path(options["path"])
        if not file_path.exists():
            raise CommandError(f"Файл не найден: {file_path}")

        ori_created = 0
        ori_updated = 0
        ds_created = 0
        ds_updated = 0
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

                responsible_person = self._get_or_create_user(row.get("Ответственное лицо") or "")
                case_number = (row.get("№ дела") or "").strip()
                sites = self._parse_sites((row.get("Сайт") or "").strip())
                industry = self._get_ref(Industry, row.get("Отрасль") or "")

                if self._is_eias_source(row):
                    defaults = {
                        "responsible_person": responsible_person,
                        "case_number": case_number,
                        "sites": sites,
                        "industry": industry,
                    }
                    obj, was_created = DataSource.objects.update_or_create(
                        inn=inn,
                        name=name,
                        defaults=defaults,
                    )
                    ds_created += int(was_created)
                    ds_updated += int(not was_created)
                    continue

                defaults = {
                    "responsible_person": responsible_person,
                    "case_number": case_number,
                    "sites": sites,
                    "industry": industry,
                    "orm_vendor": self._get_ref(OrmVendor, row.get("Производитель ТС ОРМ") or ""),
                }
                obj, was_created = Ori.objects.update_or_create(inn=inn, name=name, defaults=defaults)
                ori_created += int(was_created)
                ori_updated += int(not was_created)
                sorm_owner_links.append((obj.pk, (row.get("Владелец СОРМ") or "").strip()))

        for org_id, owner_name in sorm_owner_links:
            if not owner_name:
                continue
            owner = Ori.objects.filter(name=owner_name).first()
            if owner is None:
                continue
            Ori.objects.filter(pk=org_id).update(sorm_owner=owner)

        self.stdout.write(
            self.style.SUCCESS(
                "Импорт завершен. "
                f"ОРИ: создано {ori_created}, обновлено {ori_updated}. "
                f"Источники данных: создано {ds_created}, обновлено {ds_updated}. "
                f"Проблем: {issues}."
            )
        )
