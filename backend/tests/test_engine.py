from pathlib import Path

import pytest

from app.engine import MosaicEngine, VideoSource


class SuccessfulCapture:
    async def capture(
        self, source: VideoSource, position_seconds: float, target: Path
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"{source.id}:{position_seconds:.1f}".encode())


class SwitchableCapture(SuccessfulCapture):
    def __init__(self) -> None:
        self.failed_source_id: str | None = None

    async def capture(
        self, source: VideoSource, position_seconds: float, target: Path
    ) -> None:
        if source.id == self.failed_source_id:
            raise RuntimeError("źródło testowo niedostępne")
        await super().capture(source, position_seconds, target)


@pytest.mark.asyncio
async def test_cycle_publishes_four_synchronized_looped_frames(tmp_path: Path) -> None:
    sources = [
        VideoSource(
            id=f"film-{number}",
            title=f"Film {number}",
            path=tmp_path / f"film{number}.mp4",
            duration_seconds=10.0,
        )
        for number in range(1, 5)
    ]
    engine = MosaicEngine(
        sources=sources, capture=SuccessfulCapture(), frames_dir=tmp_path / "frames"
    )

    state = await engine.publish_cycle(playback_seconds=12.5)

    assert state.version == 1
    assert len(state.tiles) == 4
    assert {tile.batch_id for tile in state.tiles} == {state.batch_id}
    assert {tile.position_seconds for tile in state.tiles} == {2.5}
    assert {tile.status for tile in state.tiles} == {"online"}
    assert all(
        tile.frame_url.startswith(f"/frames/{state.batch_id}/") for tile in state.tiles
    )
    assert all(
        (tmp_path / "frames" / tile.frame_url.removeprefix("/frames/")).is_file()
        for tile in state.tiles
    )


@pytest.mark.asyncio
async def test_cycle_keeps_last_frame_when_one_source_fails(tmp_path: Path) -> None:
    sources = [
        VideoSource(
            id=f"film-{number}",
            title=f"Film {number}",
            path=tmp_path / f"film{number}.mp4",
            duration_seconds=30.0,
        )
        for number in range(1, 5)
    ]
    capture = SwitchableCapture()
    engine = MosaicEngine(
        sources=sources, capture=capture, frames_dir=tmp_path / "frames"
    )
    initial = await engine.publish_cycle(playback_seconds=0.0)
    previous_failed_tile = initial.tiles[-1]

    capture.failed_source_id = "film-4"
    updated = await engine.publish_cycle(playback_seconds=4.0)

    delayed_tile = updated.tiles[-1]
    assert delayed_tile.status == "delayed"
    assert delayed_tile.frame_url == previous_failed_tile.frame_url
    assert delayed_tile.captured_at == previous_failed_tile.captured_at
    assert {tile.status for tile in updated.tiles[:3]} == {"online"}


@pytest.mark.asyncio
async def test_cycle_uses_current_position_for_youtube_live_source(
    tmp_path: Path,
) -> None:
    sources = [
        VideoSource(
            id="youtube-live",
            title="YouTube Live",
            path="https://stream.example/live.m3u8",
            duration_seconds=None,
            source_type="youtube",
            webpage_url="https://www.youtube.com/watch?v=live123",
            is_live=True,
        ),
        *[
            VideoSource(
                id=f"film-{number}",
                title=f"Film {number}",
                path=tmp_path / f"film{number}.mp4",
                duration_seconds=10.0,
            )
            for number in range(2, 5)
        ],
    ]
    engine = MosaicEngine(
        sources=sources, capture=SuccessfulCapture(), frames_dir=tmp_path / "frames"
    )

    state = await engine.publish_cycle(playback_seconds=12.5)

    assert state.tiles[0].position_seconds == 0.0
    assert {tile.position_seconds for tile in state.tiles[1:]} == {2.5}
