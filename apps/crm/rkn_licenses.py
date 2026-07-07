from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html import unescape

from apps.crm.models import AppSettings, TelecomLicenseStatus, TelecomOperator, TelecomOperatorLicense

_RUSSIAN_FEDERATION_MARKER = "Российская Федерация"

_RKN_SEARCH_BASE_URL = "https://rkn.gov.ru/activity/connection/register/license/"
_RKN_DETAIL_URL = "https://rkn.gov.ru/activity/connection/register/license/?id={license_id}"
_USER_AGENT = "Mozilla/5.0 (compatible; ROTS-CRM/1.0; +https://www.rkn.gov.ru/)"
_TIMEOUT_SEC = 20


class RknSyncError(Exception):
    pass


@dataclass(frozen=True)
class ParsedLicenseRow:
    number: str
    title: str


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC, context=ctx) as resp:
            raw = resp.read()
            content_type = resp.headers.get_content_charset()
            if content_type:
                return raw.decode(content_type, errors="ignore")
            try:
                return raw.decode("utf-8", errors="ignore")
            except Exception:
                return raw.decode("cp1251", errors="ignore")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, UnicodeError) as exc:
        raise RknSyncError(f"Ошибка запроса к РКН: {exc}") from exc


def _build_search_url(inn: str) -> str:
    query = urllib.parse.urlencode(
        {
            "act": "search",
            "org_name_full": "",
            "org_inn": inn,
            "lic_num": "",
            "lic_status_id": "1",
            "service_id": "0",
            "region_id": "0",
            "searchBtn": "Найти",
        }
    )
    return f"{_RKN_SEARCH_BASE_URL}?{query}#result"


def _strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def _parse_search_rows(html: str) -> list[ParsedLicenseRow]:
    table_match = re.search(r'<table[^>]*id="ResList1"[^>]*>(.*?)</table>', html, flags=re.I | re.S)
    if not table_match:
        return []

    rows: list[ParsedLicenseRow] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), flags=re.I | re.S):
        number_match = re.search(r"<a[^>]*>(.*?)</a>", row_html, flags=re.I | re.S)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)
        if not number_match or len(cells) < 3:
            continue

        number = _strip_html(number_match.group(1))
        title = _strip_html(cells[2])
        if number:
            rows.append(ParsedLicenseRow(number=number, title=title))
    return rows


def _parse_ru_date(value: str) -> datetime.date | None:
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None


def _parse_detail_fields(html: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    row_matches = re.findall(
        r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>",
        html,
        flags=re.I | re.S,
    )
    for raw_label, raw_value in row_matches:
        label = _strip_html(raw_label).rstrip(":").lower()
        value = _strip_html(raw_value)
        if not label:
            continue
        parsed[label] = value
    return parsed


def _map_status(raw_status: str) -> str:
    value = raw_status.strip().lower()
    if "недействующ" in value or "не действующ" in value:
        return TelecomLicenseStatus.INACTIVE
    return TelecomLicenseStatus.ACTIVE


def _territory_is_allowed(territory: str, responsibility_region: str) -> bool:
    normalized = territory.strip().casefold()
    if not normalized:
        return False
    if _RUSSIAN_FEDERATION_MARKER.casefold() in normalized:
        return True
    region = responsibility_region.strip().casefold()
    return bool(region and region in normalized)


def sync_telecom_operator_licenses_from_rkn(operator: TelecomOperator) -> dict[str, int]:
    if not operator.inn:
        raise RknSyncError("У оператора отсутствует ИНН.")

    search_url = _build_search_url(operator.inn)
    search_html = _http_get(search_url)
    parsed_rows = _parse_search_rows(search_html)
    responsibility_region = AppSettings.load().responsibility_region

    existing_by_number = {x.number: x for x in operator.licenses.all()}
    created_count = 0
    newly_created_ids: set[int] = set()
    for row in parsed_rows:
        if row.number in existing_by_number:
            continue
        lic = TelecomOperatorLicense.objects.create(
            telecom_operator=operator,
            title=row.title or row.number,
            number=row.number,
        )
        existing_by_number[row.number] = lic
        newly_created_ids.add(lic.pk)
        created_count += 1

    updated_count = 0
    errors_count = 0
    skipped_territory_count = 0
    for lic in operator.licenses.all():
        if not lic.number:
            continue
        detail_id = urllib.parse.quote(lic.number, safe="")
        detail_url = _RKN_DETAIL_URL.format(license_id=detail_id)
        try:
            detail_html = _http_get(detail_url)
            detail = _parse_detail_fields(detail_html)
        except RknSyncError:
            errors_count += 1
            continue

        status_raw = detail.get("статус лицензии", "")
        start_raw = detail.get("дата предоставления лицензии", "")
        end_raw = detail.get("срок действия до", "")
        territory_raw = detail.get("территория действия лицензии", "")

        if not _territory_is_allowed(territory_raw, responsibility_region):
            skipped_territory_count += 1
            if lic.pk in newly_created_ids:
                lic.delete()
                created_count -= 1
            continue

        lic.status = _map_status(status_raw)
        lic.start_date = _parse_ru_date(start_raw)
        lic.end_date = _parse_ru_date(end_raw)
        lic.territory = territory_raw
        lic.save(update_fields=["status", "start_date", "end_date", "territory", "updated_at"])
        updated_count += 1

    return {
        "parsed_from_list": len(parsed_rows),
        "created": created_count,
        "updated": updated_count,
        "errors": errors_count,
        "skipped_territory": skipped_territory_count,
    }
