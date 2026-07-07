from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import BinaryIO

from docx import Document

from apps.crm.models import AppSettings, TelecomOperator

SUBJECTS_HEADING_MARKER = (
    "Сведения о субъектах Российской Федерации, на территориях которых оператор связи "
    "оказывает услуги связи, на отчетную дату"
)
INN_PATTERN = re.compile(
    r"Идентификационный\s+номер\s+налогоплательщика\s+ИНН:\s*(\d{10,12})",
    re.IGNORECASE,
)
NUMBERED_SECTION_PATTERN = re.compile(r"^\d+[\.)]\s")
LEADING_NUMBER_PATTERN = re.compile(r"^\d+[\.)]\s*")
LEGAL_FORM_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    ("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ", "ООО"),
    ("ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "ПАО"),
    ("НЕПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "НАО"),
    ("ЗАКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "ЗАО"),
    ("ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "ОАО"),
    ("АКЦИОНЕРНОЕ ОБЩЕСТВО", "АО"),
    ("ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ", "ИП"),
)


class ImportOutcome(str, Enum):
    REGISTERED = "registered"
    WRONG_REGION = "wrong_region"
    DUPLICATE_INN = "duplicate_inn"
    PARSE_ERROR = "parse_error"


@dataclass(frozen=True)
class ParsedTelecomOperatorReport:
    inn: str
    name: str
    correspondence_address: str


@dataclass(frozen=True)
class TelecomOperatorImportResult:
    outcome: ImportOutcome
    inn: str = ""
    name: str = ""
    operator_id: int | None = None
    message: str = ""

    def as_dict(self) -> dict:
        payload = {
            "outcome": self.outcome.value,
            "inn": self.inn,
            "name": self.name,
            "message": self.message,
        }
        if self.operator_id is not None:
            payload["operator_id"] = self.operator_id
        return payload


def _paragraphs_from_docx(source: BinaryIO) -> list[str]:
    document = Document(source)
    return [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]


def _strip_leading_number(text: str) -> str:
    return LEADING_NUMBER_PATTERN.sub("", text.strip(), count=1)


def _text_after_label(paragraph: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}\s*:?\s*(.*)$", paragraph, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def _abbreviate_legal_form(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.strip())
    upper_name = normalized.upper()
    for long_form, short_form in LEGAL_FORM_ABBREVIATIONS:
        if upper_name.startswith(long_form):
            remainder = normalized[len(long_form) :].lstrip(" ,")
            return f"{short_form} {remainder}".strip() if remainder else short_form
    return normalized


def _extract_inn(paragraphs: list[str]) -> str | None:
    for paragraph in paragraphs:
        match = INN_PATTERN.search(paragraph)
        if match:
            return match.group(1)
    return None


def _extract_organization_name(paragraphs: list[str]) -> str | None:
    for index, paragraph in enumerate(paragraphs):
        if "Тип владельца" not in paragraph:
            continue
        inline_name = _text_after_label(paragraph, "Тип владельца")
        if inline_name and inline_name.casefold() != "юридическое лицо":
            return _abbreviate_legal_form(inline_name)
        for next_paragraph in paragraphs[index + 1 :]:
            if next_paragraph.upper().startswith("ОГРН"):
                continue
            if NUMBERED_SECTION_PATTERN.match(next_paragraph):
                break
            return _abbreviate_legal_form(next_paragraph)
    return None


def _extract_correspondence_address(paragraphs: list[str]) -> str:
    label = "Адрес юридического лица"
    for index, paragraph in enumerate(paragraphs):
        normalized = _strip_leading_number(paragraph)
        if label.casefold() not in normalized.casefold():
            continue
        same_line = _text_after_label(normalized, label)
        if same_line:
            return same_line
        for next_paragraph in paragraphs[index + 1 :]:
            if NUMBERED_SECTION_PATTERN.match(next_paragraph):
                break
            return next_paragraph.strip()
    return ""


def _extract_region_subjects(paragraphs: list[str]) -> list[str]:
    for index, paragraph in enumerate(paragraphs):
        if SUBJECTS_HEADING_MARKER.casefold() not in paragraph.casefold():
            continue
        subjects: list[str] = []
        for next_paragraph in paragraphs[index + 1 :]:
            if NUMBERED_SECTION_PATTERN.match(next_paragraph):
                break
            if next_paragraph.upper().startswith("III."):
                break
            subjects.append(next_paragraph.strip())
        return subjects
    return []


def _has_target_region(paragraphs: list[str], responsibility_region: str) -> bool:
    subjects = _extract_region_subjects(paragraphs)
    if not subjects:
        return False
    marker = responsibility_region.strip().casefold()
    if not marker:
        return False
    return any(marker in subject.casefold() for subject in subjects)


def parse_telecom_operator_report(
    source: BinaryIO,
    *,
    responsibility_region: str | None = None,
) -> ParsedTelecomOperatorReport:
    paragraphs = _paragraphs_from_docx(source)
    region = responsibility_region
    if region is None:
        region = AppSettings.load().responsibility_region
    if not _has_target_region(paragraphs, region):
        raise ValueError("report_outside_region")

    inn = _extract_inn(paragraphs)
    if not inn:
        raise ValueError("inn_not_found")

    name = _extract_organization_name(paragraphs)
    if not name:
        raise ValueError("name_not_found")

    return ParsedTelecomOperatorReport(
        inn=inn,
        name=name,
        correspondence_address=_extract_correspondence_address(paragraphs),
    )


def import_telecom_operator_from_docx(source: BinaryIO, *, created_by) -> TelecomOperatorImportResult:
    try:
        parsed = parse_telecom_operator_report(source)
    except ValueError as exc:
        if str(exc) == "report_outside_region":
            return TelecomOperatorImportResult(
                outcome=ImportOutcome.WRONG_REGION,
                message="Отчёт не относится к региону ответственности",
            )
        return TelecomOperatorImportResult(
            outcome=ImportOutcome.PARSE_ERROR,
            message="Не удалось разобрать отчёт",
        )
    except Exception:
        return TelecomOperatorImportResult(
            outcome=ImportOutcome.PARSE_ERROR,
            message="Не удалось прочитать файл отчёта",
        )

    if TelecomOperator.objects.filter(inn=parsed.inn).exists():
        return TelecomOperatorImportResult(
            outcome=ImportOutcome.DUPLICATE_INN,
            inn=parsed.inn,
            name=parsed.name,
            message="Оператор с таким ИНН уже зарегистрирован",
        )

    operator = TelecomOperator.objects.create(
        inn=parsed.inn,
        name=parsed.name,
        correspondence_address=parsed.correspondence_address,
        created_by=created_by,
        updated_by=created_by,
    )
    return TelecomOperatorImportResult(
        outcome=ImportOutcome.REGISTERED,
        inn=operator.inn,
        name=operator.name,
        operator_id=operator.pk,
        message="Оператор зарегистрирован",
    )
