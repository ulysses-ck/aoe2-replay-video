"""Playback control loop: speed + camera driven by detected events."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    import pyautogui  # type: ignore
except Exception:  # pragma: no cover
    pyautogui = None  # type: ignore

from .config import Config


def _send_key(key: str, count: int = 1) -> None:
    if pyautogui is None:
        return
    for _ in range(count):
        pyautogui.press(key)
        time.sleep(0.05)


def _set_speed(cfg: Config, fast: bool) -> None:
    # Send repeated +/- to reach desired speed. Simple: send up/down a few times.
    if pyautogui is None:
        return
    key = cfg.key_speed_up if fast else cfg.key_speed_down
    # send a few taps
    for _ in range(3):
        pyautogui.press(key)
        time.sleep(0.05)


def _center_camera(cfg: Config, x: float, y: float, map_size: int) -> None:
    if pyautogui is None or cfg.minimap is None:
        return
    mx, my, mw, mh = cfg.minimap
    # map world (0..map_size) -> minimap pixels
    px = mx + int((x / max(1, map_size)) * mw)
    py = my + int((y / max(1, map_size)) * mh)
    pyautogui.click(px, py)


def run(cfg: Config) -> None:
    events = json.loads(Path(cfg.events_path).read_text()) if cfg.events_path else []
    events.sort(key=lambda e: e["t"])

    # Wait for game to load
    time.sleep(cfg.startup_wait)

    # Find window
    from .window import find_window, get_bbox, set_geometry

    win = find_window("Age of Empires", timeout=30.0)
    if win is not None:
        set_geometry(win, 0, 0, cfg.window_width, cfg.window_height)
        time.sleep(1.0)
    bbox = get_bbox(win) or (0, 0, cfg.window_width, cfg.window_height)

    from .recorder import Recorder

    rec = Recorder(cfg)
    rec.start(bbox)
    time.sleep(cfg.pre_roll)

    # Game time tracking
    game_time = 0.0  # ms
    wall_start = time.time()
    speed_fast = True
    _set_speed(cfg, True)

    i = 0
    n = len(events)
    try:
        while i < n or game_time < (events[-1]["t"] if events else 0) + 30000:
            now = time.time()
            elapsed = (now - wall_start) * 1000.0
            # advance game time by speed factor (approx)
            # We recompute each loop based on speed state
            # Use incremental: handled below
            # Simple: game_time = elapsed * current_speed
            current_speed = cfg.speed_fast if speed_fast else cfg.speed_normal
            game_time = elapsed * current_speed  # rough; better to integrate, but ok for MVP

            # Process due events
            while i < n and events[i]["t"] <= game_time:
                ev = events[i]
                # slow down for event
                if speed_fast:
                    _set_speed(cfg, False)
                    speed_fast = False
                _center_camera(cfg, ev.get("x", 0) or 0, ev.get("y", 0) or 0, cfg.map_size)
                i += 1

            # If no events pending soon, speed up
            next_t = events[i]["t"] if i < n else None
            if next_t is not None and (next_t - game_time) > 5000 and not speed_fast:
                _set_speed(cfg, True)
                speed_fast = True
                wall_start = time.time() - (game_time / (cfg.speed_fast * 1000.0))
            # exit condition
            if i >= n and game_time > (events[-1]["t"] if events else 0) + 30000:
                break
            time.sleep(0.25)
    finally:
        rec.stop()
        # restore speed
        _set_speed(cfg, True)
