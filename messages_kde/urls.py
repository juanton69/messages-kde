from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

from PySide6.QtCore import QUrl

from messages_kde.constants import (
    AUTH_HOST_SUFFIXES,
    CONVERSATIONS_URL,
    DEFAULT_START_URL,
    EXTERNAL_HOST_SUFFIXES,
    INTERNAL_HOST_SUFFIXES,
)


def host_matches(host: str, suffix: str) -> bool:
    host = (host or "").lower().rstrip(".")
    suffix = suffix.lower().rstrip(".")
    return host == suffix or host.endswith("." + suffix)


def hostname(url: QUrl | str) -> str:
    if isinstance(url, QUrl):
        return url.host().lower()
    parsed = QUrl(url)
    return parsed.host().lower() if parsed.isValid() else ""


def is_external_docs_host(host: str) -> bool:
    return any(host_matches(host, suffix) for suffix in EXTERNAL_HOST_SUFFIXES)


def is_internal_host(host: str) -> bool:
    if not host:
        return False
    if is_external_docs_host(host):
        return False
    return any(host_matches(host, suffix) for suffix in INTERNAL_HOST_SUFFIXES)


def is_auth_host(host: str) -> bool:
    return any(host_matches(host, suffix) for suffix in AUTH_HOST_SUFFIXES)


def is_messages_host(host: str) -> bool:
    return host_matches(host, "messages.google.com")


def is_http_url(url: QUrl) -> bool:
    return url.scheme() in {"http", "https"}


def should_open_externally(url: QUrl) -> bool:
    scheme = url.scheme().lower()
    if scheme in {"mailto", "tel", "geo"}:
        return True
    if scheme in {"http", "https"}:
        return not is_internal_host(url.host())
    if scheme == "sms":
        return False
    return scheme not in {"about", "blob", "data", "qrc"}


def _sms_to_messages_url(raw: str) -> QUrl:
    parsed = urlparse(raw)
    number = unquote(parsed.path or parsed.netloc or "")
    if number.startswith("//"):
        number = number[2:]
    number = number.split(";")[0].split("?")[0].strip()
    query = parse_qs(parsed.query)
    if not number and "body" not in query:
        return QUrl(CONVERSATIONS_URL)
    params = []
    if number:
        params.append("to=" + bytes(QUrl.toPercentEncoding(number)).decode("ascii"))
    body = (query.get("body") or [""])[0]
    if body:
        params.append("body=" + bytes(QUrl.toPercentEncoding(body)).decode("ascii"))
    if params:
        return QUrl(CONVERSATIONS_URL + "?" + "&".join(params))
    return QUrl(CONVERSATIONS_URL)


def convert_app_url(value: str) -> QUrl:
    raw = (value or "").strip()
    if not raw:
        return QUrl(DEFAULT_START_URL)
    if raw.startswith("sms:"):
        return _sms_to_messages_url(raw)
    url = QUrl.fromUserInput(raw)
    return url if url.isValid() else QUrl(DEFAULT_START_URL)


def parse_unread(title: str) -> int:
    text = (title or "").lstrip()
    if not text.startswith("("):
        return 0
    end = text.find(")")
    if end <= 1:
        return 0
    digits = text[1:end]
    return int(digits) if digits.isdigit() else 0
