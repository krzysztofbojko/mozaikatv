import sys
import types
from pathlib import Path

import pytest

from app.capture import FFmpegCapture
from app.engine import VideoSource
from app.youtube import ResolvedYouTubeSource, YtDlpYouTubeResolver


def make_fake_ffmpeg(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-ffmpeg"
    executable.write_text(
        """#!/usr/bin/env python3
import pathlib
import sys

arguments = sys.argv[1:]
if any("expired.example" in argument for argument in arguments):
    print("expired stream URL", file=sys.stderr)
    raise SystemExit(1)
if any("live.example" in argument for argument in arguments) and "-ss" in arguments:
    print("live input must not be seeked", file=sys.stderr)
    raise SystemExit(2)
pathlib.Path(arguments[-1]).write_bytes(b"frame")
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


class RefreshingResolver:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def resolve(self, url: str) -> ResolvedYouTubeSource:
        self.urls.append(url)
        return ResolvedYouTubeSource(
            webpage_url=url,
            stream_url="https://fresh.example/video.mp4",
            title="Film",
            duration_seconds=60.0,
            is_live=False,
        )


def test_youtube_resolver_passes_configured_cookiefile_to_yt_dlp(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured.update(options)

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, _: str, *, download: bool) -> dict[str, object]:
            assert download is False
            return {
                "url": "https://stream.example/video.mp4",
                "duration": 60,
                "webpage_url": "https://www.youtube.com/watch?v=video123",
                "title": "Film",
            }

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYoutubeDL))

    resolver = YtDlpYouTubeResolver(cookiefile=Path("/run/secrets/youtube-cookies.txt"))
    resolved = resolver._resolve_sync("https://www.youtube.com/watch?v=video123")

    assert captured["cookiefile"] == "/run/secrets/youtube-cookies.txt"
    assert resolved.stream_url == "https://stream.example/video.mp4"


@pytest.mark.asyncio
async def test_capture_reads_current_frame_from_youtube_live(tmp_path: Path) -> None:
    target = tmp_path / "frame.webp"
    source = VideoSource(
        id="live",
        title="Live",
        path="https://live.example/stream.m3u8",
        duration_seconds=None,
        source_type="youtube",
        webpage_url="https://www.youtube.com/watch?v=live123",
        is_live=True,
    )

    await FFmpegCapture(str(make_fake_ffmpeg(tmp_path))).capture(
        source, 0.0, target
    )

    assert target.read_bytes() == b"frame"


@pytest.mark.asyncio
async def test_capture_refreshes_expired_youtube_stream_url(tmp_path: Path) -> None:
    resolver = RefreshingResolver()
    target = tmp_path / "frame.webp"
    source = VideoSource(
        id="youtube",
        title="YouTube",
        path="https://expired.example/video.mp4",
        duration_seconds=60.0,
        source_type="youtube",
        webpage_url="https://www.youtube.com/watch?v=video123",
    )

    await FFmpegCapture(
        str(make_fake_ffmpeg(tmp_path)), youtube_resolver=resolver
    ).capture(source, 12.5, target)

    assert target.read_bytes() == b"frame"
    assert resolver.urls == ["https://www.youtube.com/watch?v=video123"]
    assert source.path == "https://fresh.example/video.mp4"
