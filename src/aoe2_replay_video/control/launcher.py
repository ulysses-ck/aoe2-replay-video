"""Launch AoE2 DE."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import Config


def launch_game(cfg: Config, replay_path: str | None = None) -> subprocess.Popen | None:
    rp = replay_path or cfg.replay_path
    exe = cfg.game_exe
    # Convert Windows path to WSL path if running under WSL
    if sys.platform != "win32" and exe.startswith(("D:", "C:", "d:", "c:")):
        drive = exe[0].lower()
        exe = "/mnt/" + drive + exe[2:].replace("\\", "/")
    args = [exe]
    if rp:
        # AoE2 DE accepts a replay path as argument in many versions; fall back to manual if ignored.
        rp2 = rp
        if sys.platform != "win32" and rp.startswith(("D:", "C:", "d:", "c:")):
            drive = rp[0].lower()
            rp2 = "/mnt/" + drive + rp[2:].replace("\\", "/")
        args.append(rp2)
    try:
        return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("Failed to launch game:", e)
        return None


def is_wsl() -> bool:
    return sys.platform.startswith("linux") and "microsoft" in open("/proc/version").read().lower() if Path("/proc/version").exists() else False
