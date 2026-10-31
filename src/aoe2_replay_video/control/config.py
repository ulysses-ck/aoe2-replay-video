"""Configuration for game control and capture."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    game_exe: str = r"D:\XboxGames\Age of Empires II- Definitive Edition\Content\Game\AoE2DE.exe"
    replay_path: str = ""
    events_path: str = ""   # JSON from parser
    output_path: str = "output.mp4"
    speed_fast: float = 4.0
    speed_normal: float = 1.0
    # In-game speed hotkeys (configurable). AoE2 DE defaults vary; user sets these.
    key_speed_up: str = "plus"
    key_speed_down: str = "minus"
    # Window geometry
    window_width: int = 1920
    window_height: int = 1080
    borderless: bool = True
    # Minimap rectangle on screen (x, y, w, h) for camera centering; None disables.
    minimap: tuple[int, int, int, int] | None = None
    # Map world size in tiles (for minimap mapping)
    map_size: int = 200
    # FFmpeg
    ffmpeg_preset: str = "fast"
    video_codec: str = "libx264"  # or h264_nvenc
    audio: bool = True
    # Timing
    startup_wait: float = 20.0   # seconds to wait for game to load replay
    pre_roll: float = 3.0       # record a few seconds before game time 0

    def resolve(self) -> None:
        self.output_path = str(Path(self.output_path).resolve())
