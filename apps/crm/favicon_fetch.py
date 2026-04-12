"""
Загрузка favicon по URL сайта (для автозаполнения иконки организации).
Использует только стандартную библиотеку и Pillow.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import ssl
import urllib.error
import urllib.request
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin, urlparse

from django.core.files.base import ContentFile

_MAX_HTML_BYTES = 400 * 1024
_MAX_IMAGE_BYTES = 512 * 1024
_TIMEOUT_SEC = 12
_USER_AGENT = "Mozilla/5.0 (compatible; ROTS-CRM/1.0; +https://www.w3.org/Protocols/)"

# Предпочитаем крупные иконки из разметки
_SIZE_RE = re.compile(r"^(\d+)\s*x\s*(\d+)$", re.I)


def _host_ips_safe(hostname: str) -> bool:
    """Блокируем loopback / private / link-local / multicast (базовая защита от SSRF)."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for _fam, _typ, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return bool(infos)


def _url_safe_for_fetch(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    return _host_ips_safe(host)


def _http_get_bytes(url: str, *, limit: int) -> bytes | None:
    if not _url_safe_for_fetch(url):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC, context=ctx) as resp:
            return resp.read(limit)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None


def _parse_size_score(sizes: str | None) -> int:
    if not sizes:
        return 0
    m = _SIZE_RE.match(sizes.strip())
    if not m:
        return 0
    try:
        w, h = int(m.group(1)), int(m.group(2))
        return w * h
    except ValueError:
        return 0


class _LinkIconCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        href = a.get("href", "").strip()
        if not href:
            return
        rel = a.get("rel", "").lower()
        if not any(x in rel for x in ("icon", "apple-touch", "shortcut")):
            return
        if "mask-icon" in rel:
            return
        sizes = a.get("sizes", "")
        type_ = (a.get("type") or "").lower()
        if type_ and type_.startswith("font"):
            return
        self.items.append((href, rel, sizes))


def _sorted_icon_hrefs(items: list[tuple[str, str, str]], base_url: str) -> list[str]:
    def score(rel: str, sizes: str) -> tuple[int, int]:
        s = 0
        if "apple-touch" in rel:
            s += 200
        if "icon" in rel:
            s += 50
        if "shortcut" in rel:
            s += 10
        return (s, _parse_size_score(sizes))

    ranked = sorted(items, key=lambda x: score(x[1], x[2]), reverse=True)
    out: list[str] = []
    seen: set[str] = set()
    for href, _rel, _sizes in ranked:
        full = urljoin(base_url, href)
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def _is_raster_image(data: bytes) -> bool:
    if not data or len(data) < 8:
        return False
    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as im:
            im.verify()
        return True
    except Exception:
        return False


def _to_png_thumbnail(data: bytes, max_side: int = 256) -> bytes | None:
    from PIL import Image

    try:
        buf = BytesIO(data)
        with Image.open(buf) as im:
            im.load()
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA")
            im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            out = BytesIO()
            im.save(out, format="PNG")
            return out.getvalue()
    except Exception:
        return None


def fetch_favicon_for_page_url(page_url: str) -> bytes | None:
    """
    По URL страницы сайта пытается получить растровое изображение favicon (PNG в байтах).
    """
    page_url = (page_url or "").strip()
    if not page_url:
        return None

    parsed = urlparse(page_url)
    if not parsed.scheme:
        page_url = "https://" + page_url
        parsed = urlparse(page_url)
    if parsed.scheme not in ("http", "https"):
        return None

    origin = f"{parsed.scheme}://{parsed.netloc}"

    html_bytes = _http_get_bytes(page_url, limit=_MAX_HTML_BYTES)
    candidates: list[str] = []

    if html_bytes:
        try:
            text = html_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        collector = _LinkIconCollector()
        try:
            collector.feed(text)
            collector.close()
        except Exception:
            pass
        candidates.extend(_sorted_icon_hrefs(collector.items, page_url))

    for path in ("/favicon.ico", "/favicon.png"):
        candidates.append(urljoin(origin + "/", path))

    seen: set[str] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        raw = _http_get_bytes(cand, limit=_MAX_IMAGE_BYTES)
        if not raw or not _is_raster_image(raw):
            continue
        png = _to_png_thumbnail(raw)
        if png:
            return png
    return None


def maybe_assign_favicon_from_sites(organization) -> bool:
    """
    Если у организации нет иконки, но есть сайты — подставить favicon с первого URL.
    Возвращает True, если файл иконки был записан.
    """
    if organization.icon:
        return False
    sites = organization.sites or []
    if not sites:
        return False

    png: bytes | None = None
    for raw in sites:
        url = (raw or "").strip()
        if not url:
            continue
        png = fetch_favicon_for_page_url(url)
        if png:
            break
    if not png:
        return False

    name = f"favicon_{organization.pk}.png"
    organization.icon.save(name, ContentFile(png), save=False)
    organization.save(update_fields=["icon"])
    return True
