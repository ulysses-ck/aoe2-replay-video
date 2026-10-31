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


DEBUG = False


def run(cfg: Config) -> None:
    global DEBUG
    DEBUG = getattr(cfg, "debug", False)
    events = json.loads(Path(cfg.events_path).read_text()) if cfg.events_path else []
    events.sort(key=lambda e: e["t"])
    if DEBUG:
        print(f"Loaded {len(events)} events. First: {events[0] if events else None}", flush=True)

    time.sleep(cfg.startup_wait)

    from .window import activate, find_window, get_bbox, set_geometry

    win = find_window("Age of Empires", timeout=30.0)
    if DEBUG:
        print("window:", win, flush=True)
    if win is not None:
        activate(win)
        time.sleep(0.5)
        set_geometry(win, 0, 0, cfg.window_width, cfg.window_height)
        time.sleep(1.0)
        activate(win)
    bbox = get_bbox(win) or (0, 0, cfg.window_width, cfg.window_height)
    if DEBUG:
        print("bbox:", bbox, flush=True)

    from .recorder import Recorder

    rec = Recorder(cfg)
    rec.start(bbox)
    time.sleep(cfg.pre_roll)

    game_time = 0.0
    wall_prev = time.time()
    speed_fast = True
    _set_speed(cfg, True)
    if DEBUG:
        print("Started recording. Speed: fast", flush=True)

    i = 0
    n = len(events)
    last_event_t = events[-1]["t"] if events else 0
    try:
        while True:
            now = time.time()
            dt = (now - wall_prev) * 1000.0
            current_speed = cfg.speed_fast if speed_fast else cfg.speed_normal
            game_time += dt * current_speed
            wall_prev = now

            while i < n and events[i]["t"] <= game_time:
                ev = events[i]
                if DEBUG:
                    print(f"  event @ {ev['t']}ms: {ev['type']} player={ev.get('player')}", flush=True)
                if speed_fast:
                    _set_speed(cfg, False)
                    speed_fast = False
                    if DEBUG:
                        print("    -> slow", flush=True)
                _center_camera(cfg, ev.get("x", 0) or 0, ev.get("y", 0) or 0, cfg.map_size)
                i += 1

            next_t = events[i]["t"] if i < n else None
            if next_t is not None and (next_t - game_time) > 10000 and not speed_fast:
                _set_speed(cfg, True)
                speed_fast = True
                if DEBUG:
                    print(f"  speed up (next event in {next_t - game_time:.0f}ms)", flush=True)

            if i >= n and game_time > last_event_t + 10000:
                break
            time.sleep(0.25)
    finally:
        rec.stop()
        _set_speed(cfg, True)
        if DEBUG:
            print("Done.", flush=True)
