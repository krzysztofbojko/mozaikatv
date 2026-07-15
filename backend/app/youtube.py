from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ResolvedYouTubeSource:
    webpage_url: str
    stream_url: str
    title: str
    duration_seconds: float | None
    is_live: bool


class YouTubeSourceResolver(Protocol):
    async def resolve(self, url: str) -> ResolvedYouTubeSource: ...


def validate_youtube_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    allowed_host = (
        hostname == "youtu.be"
        or hostname == "youtube.com"
        or hostname.endswith(".youtube.com")
        or hostname == "youtube-nocookie.com"
        or hostname.endswith(".youtube-nocookie.com")
    )
    if parsed.scheme not in {"http", "https"} or not allowed_host:
        raise ValueError("Podaj poprawny adres filmu lub transmisji YouTube")
    return url


class YtDlpYouTubeResolver:
    def __init__(self, max_height: int = 1080) -> None:
        self.max_height = max_height

    async def resolve(self, url: str) -> ResolvedYouTubeSource:
        validated_url = validate_youtube_url(url)
        return await asyncio.to_thread(self._resolve_sync, validated_url)

    def _resolve_sync(self, url: str) -> ResolvedYouTubeSource:
        from yt_dlp import YoutubeDL

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "format": (
                f"bestvideo[height<={self.max_height}]/"
                f"best[height<={self.max_height}]/bestvideo/best"
            ),
        }
        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=False)
        except Exception as error:
            raise RuntimeError(f"Nie można odczytać źródła YouTube: {error}") from error

        if info is None or not hasattr(info, "get"):
            raise RuntimeError("YouTube nie zwrócił informacji o źródle")

        stream_url = info.get("url")
        if not isinstance(stream_url, str) or not stream_url:
            raise RuntimeError("YouTube nie udostępnił strumienia wideo")

        is_live = info.get("is_live") is True or info.get("live_status") == "is_live"
        duration_seconds: float | None = None
        if not is_live:
            try:
                duration_seconds = float(info.get("duration"))
            except (TypeError, ValueError) as error:
                raise RuntimeError("Film YouTube nie ma poprawnego czasu trwania") from error
            if duration_seconds <= 0:
                raise RuntimeError("Film YouTube nie ma poprawnego czasu trwania")

        webpage_url = info.get("webpage_url")
        title = info.get("title")
        return ResolvedYouTubeSource(
            webpage_url=webpage_url if isinstance(webpage_url, str) else url,
            stream_url=stream_url,
            title=title if isinstance(title, str) and title.strip() else "YouTube",
            duration_seconds=duration_seconds,
            is_live=is_live,
        )
