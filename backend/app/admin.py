from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from .capture import FFmpegCapture
from .catalog import list_video_paths, probe_duration
from .engine import FrameCapture, MosaicEngine, VideoSource
from .settings import Settings
from .youtube import (
    YtDlpYouTubeResolver,
    YouTubeSourceResolver,
    validate_youtube_url,
)

DurationProbe = Callable[[Path, str], Awaitable[float]]
CaptureFactory = Callable[["AdminConfig"], FrameCapture]


class StreamConfig(BaseModel):
    slot: int = Field(ge=1, le=4)
    source_type: Literal["none", "local", "youtube"] = "local"
    filename: str = Field(default="", max_length=255)
    url: str = Field(default="", max_length=2048)
    title: str = Field(default="", max_length=80)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        stripped = value.strip()
        if stripped and Path(stripped).name != stripped:
            raise ValueError("Nazwa pliku nie może zawierać ścieżki")
        return stripped

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_source(self) -> "StreamConfig":
        if self.source_type == "none":
            self.filename = ""
            self.url = ""
            self.title = ""
            return self
        if not self.title:
            raise ValueError("Nazwa źródła nie może być pusta")
        if self.source_type == "local":
            if not self.filename:
                raise ValueError("Wybierz lokalny plik źródłowy")
            self.url = ""
        else:
            self.url = validate_youtube_url(self.url)
            self.filename = ""
        return self


class AdminConfig(BaseModel):
    refresh_min_seconds: float = Field(ge=1, le=60)
    refresh_max_seconds: float = Field(ge=1, le=60)
    frame_width: int = Field(ge=320, le=3840)
    frame_height: int = Field(ge=180, le=2160)
    webp_quality: int = Field(ge=30, le=100)
    streams: list[StreamConfig]

    @model_validator(mode="after")
    def validate_config(self) -> "AdminConfig":
        if self.refresh_min_seconds > self.refresh_max_seconds:
            raise ValueError("Minimalny interwał nie może być większy od maksymalnego")
        if self.frame_width % 2 or self.frame_height % 2:
            raise ValueError("Wymiary klatki muszą być parzyste")
        if len(self.streams) != 4 or {stream.slot for stream in self.streams} != {
            1,
            2,
            3,
            4,
        }:
            raise ValueError("Konfiguracja wymaga czterech unikalnych slotów")
        source_keys = [
            (stream.source_type, stream.filename or stream.url)
            for stream in self.streams
            if stream.source_type != "none"
        ]
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("Każdy slot musi używać innego źródła")
        self.streams.sort(key=lambda stream: stream.slot)
        return self


class AdminPayload(BaseModel):
    config: AdminConfig
    available_videos: list[str]


class AdminControl(Protocol):
    def get_payload(self) -> AdminPayload: ...

    async def apply(self, config: AdminConfig) -> AdminPayload: ...


class AdminController:
    def __init__(
        self,
        *,
        settings: Settings,
        engine: MosaicEngine,
        duration_probe: DurationProbe,
        capture_factory: CaptureFactory,
        youtube_resolver: YouTubeSourceResolver,
        config: AdminConfig,
    ) -> None:
        self.settings = settings
        self.engine = engine
        self.duration_probe = duration_probe
        self.capture_factory = capture_factory
        self.youtube_resolver = youtube_resolver
        self.config = config

    @classmethod
    async def create(
        cls,
        *,
        settings: Settings,
        engine: MosaicEngine,
        duration_probe: DurationProbe = probe_duration,
        youtube_resolver: YouTubeSourceResolver | None = None,
        capture_factory: CaptureFactory | None = None,
    ) -> "AdminController":
        videos = list_video_paths(settings.videos_dir)
        if len(videos) < 4:
            raise RuntimeError(
                f"W katalogu {settings.videos_dir} muszą znajdować się co najmniej 4 filmy"
            )
        default_config = AdminConfig(
            refresh_min_seconds=settings.refresh_min_seconds,
            refresh_max_seconds=settings.refresh_max_seconds,
            frame_width=settings.frame_width,
            frame_height=settings.frame_height,
            webp_quality=78,
            streams=[
                StreamConfig(
                    slot=index,
                    filename=path.name,
                    title=path.stem.replace("_", " ").replace("-", " ").strip()
                    or f"Źródło {index}",
                )
                for index, path in enumerate(videos[:4], start=1)
            ],
        )
        config_path = settings.runtime_dir / "config.json"
        config = default_config
        if config_path.is_file():
            try:
                config = AdminConfig.model_validate_json(
                    config_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                config = default_config

        resolver = youtube_resolver or YtDlpYouTubeResolver()
        factory = capture_factory or (
            lambda current: FFmpegCapture(
                settings.ffmpeg_bin,
                current.frame_width,
                current.frame_height,
                current.webp_quality,
                resolver,
            )
        )
        controller = cls(
            settings=settings,
            engine=engine,
            duration_probe=duration_probe,
            capture_factory=factory,
            youtube_resolver=resolver,
            config=config,
        )
        await controller._apply(config, persist=False)
        return controller

    def get_payload(self) -> AdminPayload:
        return AdminPayload(
            config=self.config,
            available_videos=[
                path.name for path in list_video_paths(self.settings.videos_dir)
            ],
        )

    async def apply(self, config: AdminConfig) -> AdminPayload:
        await self._apply(config, persist=True)
        return self.get_payload()

    async def _apply(self, config: AdminConfig, *, persist: bool) -> None:
        available = {
            path.name: path for path in list_video_paths(self.settings.videos_dir)
        }
        missing = [
            stream.filename
            for stream in config.streams
            if stream.source_type == "local" and stream.filename not in available
        ]
        if missing:
            raise ValueError(f"Brak pliku w katalogu filmy: {', '.join(missing)}")

        async def resolve_source(stream: StreamConfig) -> VideoSource:
            if stream.source_type == "none":
                return VideoSource(
                    id=f"source-{stream.slot}",
                    title="",
                    path="",
                    duration_seconds=None,
                    source_type="none",
                )
            if stream.source_type == "local":
                path = available[stream.filename]
                duration = await self.duration_probe(path, self.settings.ffprobe_bin)
                return VideoSource(
                    id=f"source-{stream.slot}",
                    title=stream.title,
                    path=path,
                    duration_seconds=duration,
                )

            resolved = await self.youtube_resolver.resolve(stream.url)
            return VideoSource(
                id=f"source-{stream.slot}",
                title=stream.title,
                path=resolved.stream_url,
                duration_seconds=resolved.duration_seconds,
                source_type="youtube",
                webpage_url=stream.url,
                is_live=resolved.is_live,
            )

        sources = list(
            await asyncio.gather(*(resolve_source(stream) for stream in config.streams))
        )
        await self.engine.reconfigure(
            sources=sources,
            capture=self.capture_factory(config),
            refresh_min_seconds=config.refresh_min_seconds,
            refresh_max_seconds=config.refresh_max_seconds,
        )
        self.config = config
        if persist:
            self._save_config(config)

    def _save_config(self, config: AdminConfig) -> None:
        self.settings.runtime_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.settings.runtime_dir / "config.json"
        temporary = config_path.with_suffix(".json.tmp")
        temporary.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, config_path)
