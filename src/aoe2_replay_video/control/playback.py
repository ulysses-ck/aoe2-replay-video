"""Playback control loop: speed + camera driven by detected events."""
from __future__ import annotations

import json
import time
from pathlib import Path

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
    """Tap the speed hotkey a few times to move between fast and normal."""
    if pyautogui is None:
        return
    key = cfg.key_speed_up if fast else cfg.key_speed_down
    for _ in range(max(1, cfg.speed_steps)):
        pyautogui.press(key)
        time.sleep(0.08)


def _center_camera(cfg: Config, x: float, y: float, map_size: int,
                   minimap: tuple[int, int, int, int]) -> None:
    """Click the minimap at the world position (x, y).

    The minimap is a flattened 2:1 isometric diamond: world (0,0) maps to the
    left vertex, (1,0) to the top, (1,1) to the right and (0,1) to the bottom.
    """
    if pyautogui is None:
        return
    mx, my, mw, mh = minimap
    n = max(1, map_size)
    u = min(1.0, max(0.0, x / n))
    v = min(1.0, max(0.0, y / n))
    cx = mx + mw / 2.0
    cy = my + mh / 2.0
    dx = (u + v - 1.0) * (mw / 2.0)
    dy = (v - u) * (mh / 2.0)
    # Keep the click inside the diamond (not just its bounding box).
    limit = 0.96
    norm = abs(dx) / (mw / 2.0) + abs(dy) / (mh / 2.0)
    if norm > limit:
        dx *= limit / norm
        dy *= limit / norm
    px = int(round(cx + dx))
    py = int(round(cy + dy))
    if DEBUG:
        print(
            f"    camera -> ({px}, {py})  [event x={x:.0f}, y={y:.0f}, "
            f"map={map_size}]",
            flush=True,
        )
    pyautogui.click(px, py)


def _resolve_map_size(cfg: Config) -> int:
    if cfg.map_size:
        return cfg.map_size
    try:
        from ..parser.replay import get_map_size

        detected = get_map_size(cfg.replay_path) if cfg.replay_path else None
    except Exception:
        detected = None
    return detected or 200


DEBUG = False


def run(cfg: Config) -> None:
    global DEBUG
    DEBUG = getattr(cfg, "debug", False)
    events = json.loads(Path(cfg.events_path).read_text()) if cfg.events_path else []
    events.sort(key=lambda e: e["t"])
    if DEBUG:
        print(f"Loaded {len(events)} events. First: {events[0] if events else None}", flush=True)

    time.sleep(cfg.startup_wait)

    from .window import activate, find_window, get_bbox, maximize

    win = find_window("Age of Empires", timeout=30.0)
    if DEBUG:
        print("window:", win, flush=True)
    if win is None:
        raise SystemExit("game window not found (title contains 'Age of Empires')")

    activate(win)
    time.sleep(0.5)
    maximize(win)
    time.sleep(1.5)
    activate(win)
    time.sleep(0.3)

    bbox = get_bbox(win)
    if bbox is None:
        bbox = (0, 0, cfg.window_width or 1366, cfg.window_height or 768)
    left, top, client_w, client_h = bbox
    minimap = cfg.resolve_minimap(client_w, client_h)
    map_size = _resolve_map_size(cfg)
    if DEBUG:
        print(f"bbox={bbox} minimap={minimap} map_size={map_size}", flush=True)

    # Zoom out so more of the action is visible.
    if pyautogui is not None and cfg.zoom_out_clicks:
        pyautogui.moveTo(left + client_w // 2, top + client_h // 2)
        time.sleep(0.3)
        for _ in range(cfg.zoom_out_clicks):
            pyautogui.scroll(-3)
            time.sleep(0.1)
        if DEBUG:
            print(f"Zoomed out ({cfg.zoom_out_clicks} clicks)", flush=True)

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
                if ev.get("x") is not None and ev.get("y") is not None:
                    _center_camera(cfg, ev["x"], ev["y"], map_size, minimap)
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
