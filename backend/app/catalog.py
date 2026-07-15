from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .engine import VideoSource

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}


async def probe_duration(path: Path, ffprobe_bin: str) -> float:
    process = await asyncio.create_subprocess_exec(
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip()
        raise RuntimeError(f"Nie można odczytać filmu {path.name}: {message}")
    try:
        duration = float(json.loads(stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Film {path.name} nie ma poprawnego czasu trwania"
        ) from error
    if duration <= 0:
        raise RuntimeError(f"Film {path.name} ma niepoprawny czas trwania")
    return duration


def list_video_paths(videos_dir: Path) -> list[Path]:
    if not videos_dir.is_dir():
        raise RuntimeError(f"Brak katalogu z filmami: {videos_dir}")

    return sorted(
        (
            path
            for path in videos_dir.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


async def discover_video_sources(
    videos_dir: Path, ffprobe_bin: str = "ffprobe"
) -> list[VideoSource]:
    paths = list_video_paths(videos_dir)
    if len(paths) < 4:
        raise RuntimeError(
            f"W katalogu {videos_dir} muszą znajdować się co najmniej 4 filmy"
        )

    selected = paths[:4]
    durations = await asyncio.gather(
        *(probe_duration(path, ffprobe_bin) for path in selected)
    )
    return [
        VideoSource(
            id=f"source-{index}",
            title=path.stem.replace("_", " ").replace("-", " ").strip()
            or f"Źródło {index}",
            path=path,
            duration_seconds=duration,
        )
        for index, (path, duration) in enumerate(
            zip(selected, durations, strict=True), start=1
        )
    ]
