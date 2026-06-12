import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.crm.models import Comment, Contact, DataSource, Event, Ori, Psi

EIAS_TYPE = "Источник ЕИАС"


class Command(BaseCommand):
    help = (
        "Переносит организации с типом «Источник ЕИАС» из CSV из модели ОРИ в «Источники данных». "
        "Сопоставление по паре ИНН + наименование."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="template/Михаил.csv",
            help="Путь к CSV файлу",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет сделано, без изменений в БД",
        )
        parser.add_argument(
            "--delete-ori",
            action="store_true",
            help="Удалить перенесённые записи из ОРИ (связанные контакты, ПСИ, комментарии и события удалятся каскадно)",
        )

    def _load_eias_keys(self, file_path: Path) -> list[tuple[str, str, int]]:
        keys: list[tuple[str, str, int]] = []
        with file_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for idx, row in enumerate(reader, start=2):
                org_type = (row.get("Тип") or "").strip()
                if org_type != EIAS_TYPE:
                    continue
                name = (row.get("Организация") or "").strip()
                inn = (row.get("ИНН") or "").strip()
                if not name or not inn:
                    self.stdout.write(self.style.WARNING(f"Строка {idx}: пропущена, нет названия или ИНН"))
                    continue
                keys.append((inn, name, idx))
        return keys

    def _related_counts(self, ori: Ori) -> dict[str, int]:
        return {
            "contacts": Contact.objects.filter(organization_id=ori.pk).count(),
            "psis": Psi.objects.filter(organization_id=ori.pk).count(),
            "comments": Comment.objects.filter(organization_id=ori.pk).count(),
            "events": Event.objects.filter(organization_id=ori.pk).count(),
            "sorm_children": Ori.objects.filter(sorm_owner_id=ori.pk).count(),
        }

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = Path(options["path"])
        if not file_path.exists():
            raise CommandError(f"Файл не найден: {file_path}")

        dry_run = options["dry_run"]
        delete_ori = options["delete_ori"]
        eias_keys = self._load_eias_keys(file_path)
        if not eias_keys:
            self.stdout.write(self.style.WARNING("В CSV не найдено записей с типом «Источник ЕИАС»."))
            return

        created = 0
        updated = 0
        skipped = 0
        not_found = 0
        deleted = 0

        for inn, name, row_num in eias_keys:
            ori = Ori.objects.filter(inn=inn, name=name).first()
            if ori is None:
                not_found += 1
                self.stdout.write(
                    self.style.WARNING(f"Строка {row_num}: ОРИ не найдена — {name} ({inn})")
                )
                continue

            existing_ds = DataSource.objects.filter(inn=inn, name=name).first()
            related = self._related_counts(ori)
            related_total = sum(related.values())

            if dry_run:
                action = "обновить" if existing_ds else "создать"
                self.stdout.write(
                    f"[dry-run] Строка {row_num}: {action} DataSource для {name} ({inn}); "
                    f"связей с ОРИ: {related_total} ({related})"
                )
                if delete_ori:
                    self.stdout.write(f"[dry-run] удалить ОРИ pk={ori.pk}")
                continue

            data = {
                "icon": ori.icon,
                "case_number": ori.case_number,
                "responsible_person": ori.responsible_person,
                "sites": ori.sites,
                "correspondence_address": ori.correspondence_address,
                "industry": ori.industry,
            }
            if existing_ds:
                for field, value in data.items():
                    setattr(existing_ds, field, value)
                existing_ds.save()
                updated += 1
                data_source = existing_ds
            else:
                data_source = DataSource.objects.create(inn=inn, name=name, **data)
                created += 1

            if related_total:
                self.stdout.write(
                    self.style.WARNING(
                        f"Строка {row_num}: {name} — у ОРИ есть связанные записи: {related}"
                    )
                )

            if delete_ori:
                Ori.objects.filter(sorm_owner_id=ori.pk).update(sorm_owner=None)
                ori.delete()
                deleted += 1
            else:
                skipped += 1
                self.stdout.write(
                    f"Строка {row_num}: DataSource pk={data_source.pk} готов; "
                    f"ОРИ pk={ori.pk} оставлена (укажите --delete-ori для удаления)"
                )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry-run: в CSV {len(eias_keys)} записей «Источник ЕИАС». "
                    f"Запустите без --dry-run для переноса."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. DataSource: создано {created}, обновлено {updated}. "
                f"ОРИ не найдено: {not_found}. "
                f"ОРИ удалено: {deleted}. ОРИ оставлено: {skipped}."
            )
        )
