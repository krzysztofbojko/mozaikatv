from pathlib import Path

import httpx
import pytest

from app.admin import AdminController
from app.engine import MosaicEngine, VideoSource
from app.main import create_app
from app.settings import Settings
from app.youtube import ResolvedYouTubeSource


class SuccessfulCapture:
    async def capture(
        self, source: VideoSource, position_seconds: float, target: Path
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"frame")


@pytest.mark.asyncio
async def test_admin_api_updates_and_persists_running_configuration(
    tmp_path: Path,
) -> None:
    videos_dir = tmp_path / "filmy"
    videos_dir.mkdir()
    for number in range(1, 5):
        (videos_dir / f"film{number}.mp4").write_bytes(b"test")

    settings = Settings(
        videos_dir=videos_dir,
        runtime_dir=tmp_path / "runtime",
        ffmpeg_bin="ffmpeg",
        ffprobe_bin="ffprobe",
        refresh_min_seconds=3,
        refresh_max_seconds=5,
        frame_width=960,
        frame_height=540,
        retained_batches=30,
    )
    initial_sources = [
        VideoSource(
            f"source-{number}", f"Film {number}", videos_dir / f"film{number}.mp4", 60
        )
        for number in range(1, 5)
    ]
    engine = MosaicEngine(initial_sources, SuccessfulCapture(), settings.frames_dir)

    async def duration_probe(_: Path, __: str) -> float:
        return 60.0

    controller = await AdminController.create(
        settings=settings,
        engine=engine,
        duration_probe=duration_probe,
        capture_factory=lambda _: SuccessfulCapture(),
    )
    app = create_app(
        engine=engine,
        settings=settings,
        admin_controller=controller,
        start_engine=False,
    )
    update = {
        "refresh_min_seconds": 2.5,
        "refresh_max_seconds": 4.5,
        "frame_width": 1280,
        "frame_height": 720,
        "webp_quality": 82,
        "streams": [
                {
                    "slot": number,
                    "source_type": "local",
                    "filename": f"film{5 - number}.mp4",
                    "url": "",
                    "title": f"Kamera {number}",
                }
            for number in range(1, 5)
        ],
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            before = await client.get("/api/admin/config")
            saved = await client.put("/api/admin/config", json=update)
            after = await client.get("/api/admin/config")

    assert before.status_code == 200
    assert before.json()["available_videos"] == [
        "film1.mp4",
        "film2.mp4",
        "film3.mp4",
        "film4.mp4",
    ]
    assert saved.status_code == 200
    assert after.json()["config"] == update
    assert engine.refresh_min_seconds == 2.5
    assert engine.refresh_max_seconds == 4.5
    assert [source.title for source in engine.sources] == [
        "Kamera 1",
        "Kamera 2",
        "Kamera 3",
        "Kamera 4",
    ]
    assert (settings.runtime_dir / "config.json").is_file()


class FakeYouTubeResolver:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def resolve(self, url: str) -> ResolvedYouTubeSource:
        self.urls.append(url)
        if "live123" in url:
            return ResolvedYouTubeSource(
                webpage_url=url,
                stream_url="https://stream.example/live.m3u8",
                title="Kanał na żywo",
                duration_seconds=None,
                is_live=True,
            )
        return ResolvedYouTubeSource(
            webpage_url=url,
            stream_url="https://stream.example/video.mp4",
            title="Film z YouTube",
            duration_seconds=125.0,
            is_live=False,
        )


@pytest.mark.asyncio
async def test_admin_api_accepts_youtube_video_and_live_sources(
    tmp_path: Path,
) -> None:
    videos_dir = tmp_path / "filmy"
    videos_dir.mkdir()
    for number in range(1, 5):
        (videos_dir / f"film{number}.mp4").write_bytes(b"test")

    settings = Settings(
        videos_dir=videos_dir,
        runtime_dir=tmp_path / "runtime",
        ffmpeg_bin="ffmpeg",
        ffprobe_bin="ffprobe",
        refresh_min_seconds=3,
        refresh_max_seconds=5,
        frame_width=960,
        frame_height=540,
        retained_batches=30,
    )
    engine = MosaicEngine(
        [
            VideoSource(
                f"source-{number}",
                f"Film {number}",
                videos_dir / f"film{number}.mp4",
                60,
            )
            for number in range(1, 5)
        ],
        SuccessfulCapture(),
        settings.frames_dir,
    )

    async def duration_probe(_: Path, __: str) -> float:
        return 60.0

    resolver = FakeYouTubeResolver()
    controller = await AdminController.create(
        settings=settings,
        engine=engine,
        duration_probe=duration_probe,
        youtube_resolver=resolver,
        capture_factory=lambda _: SuccessfulCapture(),
    )
    app = create_app(
        engine=engine,
        settings=settings,
        admin_controller=controller,
        start_engine=False,
    )
    update = {
        "refresh_min_seconds": 3,
        "refresh_max_seconds": 5,
        "frame_width": 960,
        "frame_height": 540,
        "webp_quality": 78,
        "streams": [
            {
                "slot": 1,
                "source_type": "youtube",
                "filename": "",
                "url": "https://youtu.be/video123",
                "title": "YouTube Film",
            },
            {
                "slot": 2,
                "source_type": "youtube",
                "filename": "",
                "url": "https://www.youtube.com/watch?v=live123",
                "title": "YouTube Live",
            },
            {
                "slot": 3,
                "source_type": "local",
                "filename": "film3.mp4",
                "url": "",
                "title": "Lokalny 3",
            },
            {
                "slot": 4,
                "source_type": "local",
                "filename": "film4.mp4",
                "url": "",
                "title": "Lokalny 4",
            },
        ],
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            saved = await client.put("/api/admin/config", json=update)

    assert saved.status_code == 200, saved.text
    assert saved.json()["config"] == update
    assert resolver.urls == [
        "https://youtu.be/video123",
        "https://www.youtube.com/watch?v=live123",
    ]
    assert engine.sources[0].source_type == "youtube"
    assert engine.sources[0].path == "https://stream.example/video.mp4"
    assert engine.sources[0].duration_seconds == 125.0
    assert engine.sources[0].is_live is False
    assert engine.sources[1].source_type == "youtube"
    assert engine.sources[1].path == "https://stream.example/live.m3u8"
    assert engine.sources[1].duration_seconds is None
    assert engine.sources[1].is_live is True
