from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import AppSettings, TelecomOperator
from apps.crm.rkn_licenses import _territory_is_allowed
from apps.crm.telecom_operator_import import (
    ImportOutcome,
    import_telecom_operator_from_docx,
    parse_telecom_operator_report,
)

User = get_user_model()


def _rkn_dir() -> Path | None:
    for path in Path(".").iterdir():
        if path.is_dir() and any(path.glob("778386080*.docx")):
            return path
    return None


class TelecomOperatorImportTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rkn_dir = _rkn_dir()

    def setUp(self):
        self.user = User.objects.create_user(username="import_tester", password="test-pass")
        settings = AppSettings.load()
        settings.responsibility_region = "Краснодарский край"
        settings.save()

    def _open_sample(self, prefix: str):
        if self.rkn_dir is None:
            self.skipTest("Папка с примерами отчётов РКН не найдена")
        matches = sorted(self.rkn_dir.glob(f"{prefix}*.docx"))
        if not matches:
            self.skipTest(f"Файл {prefix} не найден")
        return matches[0].open("rb")

    def test_parse_valid_report(self):
        with self._open_sample("778388750") as report:
            parsed = parse_telecom_operator_report(report)
        self.assertEqual(parsed.inn, "2345008861")
        self.assertEqual(parsed.name, 'ЗАО ФИРМА "ОТРАДА"')
        self.assertIn("Краснодарский", parsed.correspondence_address)

    def test_reject_report_without_region(self):
        with self._open_sample("778386080") as report:
            with self.assertRaises(ValueError):
                parse_telecom_operator_report(report)

    def test_import_registers_operator(self):
        with self._open_sample("778388750") as report:
            result = import_telecom_operator_from_docx(report, created_by=self.user)
        self.assertEqual(result.outcome, ImportOutcome.REGISTERED)
        self.assertTrue(TelecomOperator.objects.filter(inn="2345008861").exists())

    def test_import_skips_duplicate_inn(self):
        TelecomOperator.objects.create(
            inn="2345008861",
            name='ЗАО ФИРМА "ОТРАДА"',
            created_by=self.user,
        )
        with self._open_sample("778388750") as report:
            result = import_telecom_operator_from_docx(report, created_by=self.user)
        self.assertEqual(result.outcome, ImportOutcome.DUPLICATE_INN)

    def test_import_skips_wrong_region(self):
        with self._open_sample("778410225") as report:
            result = import_telecom_operator_from_docx(report, created_by=self.user)
        self.assertEqual(result.outcome, ImportOutcome.WRONG_REGION)

    def test_import_uses_app_settings_region(self):
        settings = AppSettings.load()
        settings.responsibility_region = "Свердловская область"
        settings.save()
        with self._open_sample("778386080") as report:
            result = import_telecom_operator_from_docx(report, created_by=self.user)
        self.assertEqual(result.outcome, ImportOutcome.REGISTERED)


class RknLicenseTerritoryFilterTests(TestCase):
    def test_allows_russian_federation(self):
        self.assertTrue(_territory_is_allowed("Российская Федерация", "Краснодарский край"))

    def test_allows_responsibility_region(self):
        self.assertTrue(
            _territory_is_allowed(
                "Краснодарский край, Республика Адыгея",
                "Краснодарский край",
            )
        )

    def test_rejects_unrelated_region(self):
        self.assertFalse(
            _territory_is_allowed(
                "Свердловская область",
                "Краснодарский край",
            )
        )

    def test_rejects_empty_territory(self):
        self.assertFalse(_territory_is_allowed("", "Краснодарский край"))
