"""Configuration for game control and capture."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    game_exe: str = os.environ.get(
        "AOE2_GAME_EXE",
        r"D:\XboxGames\Age of Empires II- Definitive Edition\Content\gamelaunchhelper.exe",
    )
    replay_path: str = ""
    events_path: str = ""   # JSON from parser
    output_path: str = "output.mp4"
    speed_fast: float = 4.0
    speed_normal: float = 1.0
    # In-game speed hotkeys (configurable). AoE2 DE defaults vary; user sets these.
    key_speed_up: str = "add"       # numpad + (bind in AoE2 DE)
    key_speed_down: str = "subtract" # numpad - (bind in AoE2 DE)
    # How many taps to move one speed tier at a time (fast <-> normal).
    speed_steps: int = 3
    # Window geometry. 0 means "maximize and use the full client area".
    window_width: int = 0
    window_height: int = 0
    borderless: bool = True
    # Minimap rectangle on screen (x, y, w, h). None = derive from client size
    # using the fractions below (measured at 1366x768 maximize).
    minimap: tuple[int, int, int, int] | None = None
    minimap_center: tuple[float, float] = (0.87555, 0.89323)
    minimap_size: tuple[float, float] = (0.22108, 0.20833)
    # Map world size in tiles; 0 = auto-detect from the replay header.
    map_size: int = 0
    # FFmpeg
    ffmpeg_preset: str = "fast"
    video_codec: str = "libx264"  # or h264_nvenc
    audio: bool = True
    # Timing
    startup_wait: float = 5.0   # seconds to wait for game to load replay
    pre_roll: float = 3.0       # record a few seconds before game time 0
    debug: bool = False
    # Zoom
    zoom_out_clicks: int = 8   # mouse wheel clicks to zoom out at start

    def resolve(self) -> None:
        self.output_path = str(Path(self.output_path).resolve())

    def resolve_minimap(self, client_w: int, client_h: int) -> tuple[int, int, int, int]:
        """Return the minimap bbox in screen pixels for a given client size."""
        if self.minimap is not None:
            return self.minimap
        cx = self.minimap_center[0] * client_w
        cy = self.minimap_center[1] * client_h
        w = self.minimap_size[0] * client_w
        h = self.minimap_size[1] * client_h
        return (
            int(round(cx - w / 2.0)),
            int(round(cy - h / 2.0)),
            int(round(w)),
            int(round(h)),
        )
