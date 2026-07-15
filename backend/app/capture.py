from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from .engine import VideoSource
from .youtube import YouTubeSourceResolver


class FFmpegCapture:
    def __init__(
        self,
        ffmpeg_bin: str = "ffmpeg",
        width: int = 960,
        height: int = 540,
        quality: int = 78,
        youtube_resolver: YouTubeSourceResolver | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.width = width
        self.height = height
        self.quality = quality
        self.youtube_resolver = youtube_resolver
        self.timeout_seconds = timeout_seconds

    async def capture(
        self, source: VideoSource, position_seconds: float, target: Path
    ) -> None:
        try:
            await self._capture_once(source, position_seconds, target)
        except RuntimeError:
            if (
                source.source_type != "youtube"
                or not source.webpage_url
                or self.youtube_resolver is None
            ):
                raise
            resolved = await self.youtube_resolver.resolve(source.webpage_url)
            source.path = resolved.stream_url
            source.duration_seconds = resolved.duration_seconds
            source.is_live = resolved.is_live
            await self._capture_once(source, position_seconds, target)

    async def _capture_once(
        self, source: VideoSource, position_seconds: float, target: Path
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.stem}-{uuid4().hex}.webp")
        video_filter = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=0x07090d"
        )
        input_arguments = ["-i", str(source.path)]
        if not source.is_live:
            input_arguments = ["-ss", f"{position_seconds:.3f}", *input_arguments]
        process = await asyncio.create_subprocess_exec(
            self.ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            *input_arguments,
            "-frames:v",
            "1",
            "-an",
            "-vf",
            video_filter,
            "-c:v",
            "libwebp",
            "-quality",
            str(self.quality),
            "-compression_level",
            "4",
            "-y",
            str(temporary),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except TimeoutError as error:
            process.kill()
            await process.communicate()
            temporary.unlink(missing_ok=True)
            raise RuntimeError(
                f"FFmpeg dla {source.title}: przekroczono czas oczekiwania"
            ) from error
        if process.returncode != 0:
            temporary.unlink(missing_ok=True)
            message = stderr.decode(errors="replace").strip()
            raise RuntimeError(f"FFmpeg dla {source.title}: {message[-800:]}")
        os.replace(temporary, target)
