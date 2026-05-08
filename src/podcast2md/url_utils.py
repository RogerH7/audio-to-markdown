from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse, urlunparse


URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+", re.IGNORECASE)
BARE_URL_RE = re.compile(
    r"\b((?:www\.)?(?:bilibili\.com|youtube\.com|youtu\.be|xiaoyuzhoufm\.com|b23\.tv)/[^\s<>\]\)\"']+)",
    re.IGNORECASE,
)


def normalize_url(url: str) -> str:
    url = url.strip().rstrip(".,;，。；、")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.scheme == "http" and _is_common_media_host(parsed.netloc.lower()):
        parsed = parsed._replace(scheme="https")
    if parsed.netloc.lower() == "bilibili.com":
        parsed = parsed._replace(netloc="www.bilibili.com")
    url = urlunparse(parsed)
    return url


def _is_common_media_host(host: str) -> bool:
    return any(
        domain in host
        for domain in (
            "bilibili.com",
            "b23.tv",
            "youtube.com",
            "youtu.be",
            "xiaoyuzhoufm.com",
        )
    )


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in URL_RE.findall(text or ""):
        url = normalize_url(match)
        if url not in urls:
            urls.append(url)
    for match in BARE_URL_RE.findall(text or ""):
        url = normalize_url(match)
        if url not in urls:
            urls.append(url)
    return urls


def source_platform(url: str) -> str:
    url = normalize_url(url)
    host = urlparse(url).netloc.lower()
    if "bilibili.com" in host or host == "b23.tv":
        return "bilibili"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "xiaoyuzhoufm.com" in host:
        return "xiaoyuzhou"
    if host.endswith("rss.com") or "feed" in host:
        return "podcast"
    if re.search(r"\.(mp3|m4a|wav|flac|aac|ogg)(\?|$)", url, re.IGNORECASE):
        return "audio"
    return "generic"


def dedupe_key(url: str) -> str:
    normalized = normalize_url(url)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def safe_filename(text: str, fallback: str = "untitled") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\n\r\t]+', "_", text).strip(" ._")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:160] or fallback
