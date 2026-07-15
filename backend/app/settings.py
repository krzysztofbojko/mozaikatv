from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    videos_dir: Path
    runtime_dir: Path
    ffmpeg_bin: str
    ffprobe_bin: str
    refresh_min_seconds: float
    refresh_max_seconds: float
    frame_width: int
    frame_height: int
    retained_batches: int

    @property
    def frames_dir(self) -> Path:
        return self.runtime_dir / "frames"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            videos_dir=Path(os.getenv("MOSAIC_VIDEOS_DIR", "filmy")).resolve(),
            runtime_dir=Path(os.getenv("MOSAIC_RUNTIME_DIR", "runtime")).resolve(),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
            ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
            refresh_min_seconds=float(os.getenv("MOSAIC_REFRESH_MIN", "3")),
            refresh_max_seconds=float(os.getenv("MOSAIC_REFRESH_MAX", "5")),
            frame_width=int(os.getenv("MOSAIC_FRAME_WIDTH", "960")),
            frame_height=int(os.getenv("MOSAIC_FRAME_HEIGHT", "540")),
            retained_batches=int(os.getenv("MOSAIC_RETAINED_BATCHES", "30")),
        )
