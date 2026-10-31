"""Screen/window recording via ffmpeg."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any

from .config import Config


class Recorder:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.proc: subprocess.Popen | None = None

    def start(self, bbox: tuple[int, int, int, int] | None = None) -> None:
        if bbox is None:
            w, h = self.cfg.window_width, self.cfg.window_height
            if not w or not h:
                try:
                    import pyautogui  # type: ignore

                    size = pyautogui.size()
                    w, h = size.width, size.height
                except Exception:
                    w, h = 1366, 768
            bbox = (0, 0, w, h)
        left, top, w, h = bbox
        # align to even dimensions for h264
        w -= w % 2
        h -= h % 2
        if sys.platform == "win32":
            inp = ["-f", "gdigrab", "-draw_mouse", "0", "-framerate", "30", "-offset_x", str(left), "-offset_y", str(top), "-video_size", f"{w}x{h}", "-i", "desktop"]
        else:
            inp = ["-f", "x11grab", "-framerate", "30", "-video_size", f"{w}x{h}", "-i", f":0.0+{left},{top}"]
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + inp
        if self.cfg.video_codec:
            cmd += ["-c:v", self.cfg.video_codec, "-preset", self.cfg.ffmpeg_preset]
        if self.cfg.audio:
            if sys.platform == "win32":
                cmd += ["-f", "dshow", "-i", "audio=Microphone (Realtek(R) Audio)"]
            # audio optional; skip if not available
        cmd += [self.cfg.output_path]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self) -> None:
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
            self.proc = None
