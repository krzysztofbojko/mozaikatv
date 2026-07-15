from __future__ import annotations

import asyncio
import os
import random
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel


@dataclass(slots=True)
class VideoSource:
    id: str
    title: str
    path: Path | str
    duration_seconds: float | None
    source_type: Literal["none", "local", "youtube"] = "local"
    webpage_url: str | None = None
    is_live: bool = False


class FrameCapture(Protocol):
    async def capture(
        self, source: VideoSource, position_seconds: float, target: Path
    ) -> None: ...


class TileSnapshot(BaseModel):
    source_id: str
    title: str
    batch_id: str
    frame_url: str
    captured_at: datetime
    position_seconds: float
    status: Literal["online", "delayed", "offline", "disabled"]
    error: str | None = None


class MosaicState(BaseModel):
    version: int
    batch_id: str
    published_at: datetime
    next_refresh_seconds: float | None = None
    tiles: list[TileSnapshot]


class MosaicEngine:
    def __init__(
        self,
        sources: list[VideoSource],
        capture: FrameCapture,
        frames_dir: Path,
        refresh_min_seconds: float = 3.0,
        refresh_max_seconds: float = 5.0,
        retained_batches: int = 30,
        rng: random.Random | None = None,
    ) -> None:
        if len(sources) != 4:
            raise ValueError("Silnik mozaiki wymaga dokładnie czterech źródeł")
        if refresh_min_seconds <= 0 or refresh_min_seconds > refresh_max_seconds:
            raise ValueError("Niepoprawny zakres odświeżania")
        self.sources = sources
        self.capture = capture
        self.frames_dir = frames_dir
        self.refresh_min_seconds = refresh_min_seconds
        self.refresh_max_seconds = refresh_max_seconds
        self.retained_batches = retained_batches
        self.rng = rng or random.Random()
        self._version = 0
        self._state: MosaicState | None = None
        self._condition = asyncio.Condition()
        self._stop_event = asyncio.Event()
        self._cycle_lock = asyncio.Lock()
        self._playback_started_at = time.monotonic()

    @property
    def current_state(self) -> MosaicState | None:
        return self._state

    async def publish_cycle(
        self,
        playback_seconds: float,
        next_refresh_seconds: float | None = None,
    ) -> MosaicState:
        async with self._cycle_lock:
            return await self._publish_cycle(playback_seconds, next_refresh_seconds)

    async def _publish_cycle(
        self,
        playback_seconds: float,
        next_refresh_seconds: float | None = None,
    ) -> MosaicState:
        self._version += 1
        captured_at = datetime.now(UTC)
        batch_id = f"{captured_at:%Y%m%dT%H%M%S%fZ}-{self._version:06d}"
        batch_dir = self.frames_dir / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        positions: dict[str, float] = {}
        for source in self.sources:
            if source.source_type == "none":
                positions[source.id] = 0.0
                continue
            if source.is_live:
                positions[source.id] = 0.0
                continue
            if source.duration_seconds is None or source.duration_seconds <= 0:
                raise RuntimeError(
                    f"Źródło {source.title} nie ma poprawnego czasu trwania"
                )
            positions[source.id] = playback_seconds % source.duration_seconds
        targets = {
            source.id: batch_dir / f"{source.id}.webp" for source in self.sources
        }

        async def capture_source(source: VideoSource) -> None:
            if source.source_type != "none":
                await self.capture.capture(
                    source, positions[source.id], targets[source.id]
                )

        results = await asyncio.gather(
            *(capture_source(source) for source in self.sources),
            return_exceptions=True,
        )

        previous_tiles = (
            {tile.source_id: tile for tile in self._state.tiles} if self._state else {}
        )
        tiles: list[TileSnapshot] = []
        for source, result in zip(self.sources, results, strict=True):
            if source.source_type == "none":
                tiles.append(
                    TileSnapshot(
                        source_id=source.id,
                        title="",
                        batch_id=batch_id,
                        frame_url="",
                        captured_at=captured_at,
                        position_seconds=0.0,
                        status="disabled",
                    )
                )
                continue
            if not isinstance(result, BaseException):
                tiles.append(
                    TileSnapshot(
                        source_id=source.id,
                        title=source.title,
                        batch_id=batch_id,
                        frame_url=f"/frames/{batch_id}/{source.id}.webp",
                        captured_at=captured_at,
                        position_seconds=round(positions[source.id], 3),
                        status="online",
                    )
                )
                continue

            previous = previous_tiles.get(source.id)
            if previous:
                tiles.append(
                    previous.model_copy(
                        update={"status": "delayed", "error": str(result)}
                    )
                )
            else:
                tiles.append(
                    TileSnapshot(
                        source_id=source.id,
                        title=source.title,
                        batch_id=batch_id,
                        frame_url="",
                        captured_at=captured_at,
                        position_seconds=round(positions[source.id], 3),
                        status="offline",
                        error=str(result),
                    )
                )

        self._state = MosaicState(
            version=self._version,
            batch_id=batch_id,
            published_at=captured_at,
            next_refresh_seconds=next_refresh_seconds,
            tiles=tiles,
        )
        self._write_manifest(self._state)
        self._cleanup_old_batches()
        async with self._condition:
            self._condition.notify_all()
        return self._state

    async def run_forever(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            cycle_started_at = time.monotonic()
            interval = self.rng.uniform(
                self.refresh_min_seconds, self.refresh_max_seconds
            )
            await self.publish_cycle(
                playback_seconds=cycle_started_at - self._playback_started_at,
                next_refresh_seconds=round(interval, 2),
            )
            remaining = max(0.05, interval - (time.monotonic() - cycle_started_at))
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=remaining)
            except TimeoutError:
                pass

    async def reconfigure(
        self,
        *,
        sources: list[VideoSource],
        capture: FrameCapture,
        refresh_min_seconds: float,
        refresh_max_seconds: float,
    ) -> None:
        if len(sources) != 4:
            raise ValueError("Silnik mozaiki wymaga dokładnie czterech źródeł")
        if refresh_min_seconds <= 0 or refresh_min_seconds > refresh_max_seconds:
            raise ValueError("Niepoprawny zakres odświeżania")
        async with self._cycle_lock:
            self.sources = sources
            self.capture = capture
            self.refresh_min_seconds = refresh_min_seconds
            self.refresh_max_seconds = refresh_max_seconds
            self._playback_started_at = time.monotonic()

    def stop(self) -> None:
        self._stop_event.set()

    async def wait_for_update(self, after_version: int) -> MosaicState:
        async with self._condition:
            await self._condition.wait_for(
                lambda: self._state is not None and self._state.version > after_version
            )
        assert self._state is not None
        return self._state

    def _write_manifest(self, state: MosaicState) -> None:
        manifest = self.frames_dir.parent / "manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        temporary = manifest.with_suffix(".json.tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, manifest)

    def _cleanup_old_batches(self) -> None:
        if not self.frames_dir.is_dir():
            return
        batches = sorted(
            (path for path in self.frames_dir.iterdir() if path.is_dir()), reverse=True
        )
        protected = {
            tile.frame_url.split("/")[2]
            for tile in (self._state.tiles if self._state else [])
            if tile.frame_url.startswith("/frames/")
        }
        for batch in batches[self.retained_batches :]:
            if batch.name not in protected:
                shutil.rmtree(batch, ignore_errors=True)
