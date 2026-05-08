from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .url_utils import normalize_url, safe_filename, source_platform


@dataclass
class DownloadResult:
    audio_path: Path
    title: str
    metadata: dict[str, Any]


def _download_direct_audio(url: str, output_dir: str | Path) -> DownloadResult:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = safe_filename(Path(url.split("?", 1)[0]).name, "audio")
    target = output_dir / name
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with target.open("wb") as f:
            shutil.copyfileobj(resp.raw, f)
    return DownloadResult(target, target.stem, {"source_url": url, "platform": "audio"})


def download_source(
    url: str,
    output_dir: str | Path,
    *,
    cookie_file: str | None = None,
    cookies_from_browser: str | None = None,
) -> DownloadResult:
    url = normalize_url(url)
    platform = source_platform(url)
    if platform == "audio":
        return _download_direct_audio(url, output_dir)

    import yt_dlp

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded_paths: list[Path] = []

    def hook(info: dict[str, Any]) -> None:
        if info.get("status") == "finished" and info.get("filename"):
            downloaded_paths.append(Path(info["filename"]))

    opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(extractor_key)s-%(id)s-%(title).140B.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }
        ],
        "postprocessor_hooks": [hook],
        "quiet": True,
        "noplaylist": True,
        "retries": 3,
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "http_headers": {
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        },
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title") or info.get("fulltitle") or "untitled"
        prepared = Path(ydl.prepare_filename(info))

    candidates = []
    for path in downloaded_paths:
        candidates.append(path.with_suffix(".mp3"))
        candidates.append(path)
    candidates.append(prepared.with_suffix(".mp3"))
    candidates.append(prepared)
    for candidate in candidates:
        if candidate.exists():
            return DownloadResult(
                candidate,
                title,
                {
                    "source_url": url,
                    "platform": platform,
                    "extractor": info.get("extractor_key"),
                    "uploader": info.get("uploader") or info.get("channel"),
                    "duration": info.get("duration"),
                    "webpage_url": info.get("webpage_url") or url,
                },
            )

    raise FileNotFoundError(f"Downloaded audio file was not found for URL: {url}")
