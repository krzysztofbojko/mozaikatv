from pathlib import Path

import httpx
import pytest

from app.engine import MosaicEngine, VideoSource
from app.main import create_app


class SuccessfulCapture:
    async def capture(
        self, source: VideoSource, position_seconds: float, target: Path
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"frame")


@pytest.mark.asyncio
async def test_http_interface_exposes_current_mosaic_and_health(tmp_path: Path) -> None:
    sources = [
        VideoSource(
            f"film-{number}", f"Film {number}", tmp_path / f"{number}.mp4", 60.0
        )
        for number in range(1, 5)
    ]
    engine = MosaicEngine(sources, SuccessfulCapture(), tmp_path / "frames")
    app = create_app(engine=engine, start_engine=False)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            empty = await client.get("/api/mosaic")
            health = await client.get("/api/health")

    assert empty.status_code == 503
    assert health.status_code == 200
    assert health.json() == {"status": "starting", "version": 0, "sources": []}
