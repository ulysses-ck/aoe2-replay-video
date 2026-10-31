"""CLI entrypoint for control + capture."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import Config
from .playback import run


def main() -> None:
    ap = argparse.ArgumentParser(description="AoE2 replay auto-record")
    ap.add_argument("--game-exe", default=None)
    ap.add_argument("--replay", required=True)
    ap.add_argument("--events", required=True, help="events JSON from parser")
    ap.add_argument("--output", default="output.mp4")
    ap.add_argument("--speed-fast", type=float, default=4.0)
    ap.add_argument("--map-size", type=int, default=0,
                    help="map size in tiles; 0 = detect from the replay header")
    ap.add_argument("--minimap", default=None,
                    help="x,y,w,h of the minimap in screen pixels; "
                         "omit to derive it from the game client size")
    ap.add_argument("--zoom-out", type=int, default=8,
                    help="mouse wheel clicks to zoom out at start")
    ap.add_argument("--speed-steps", type=int, default=3,
                    help="hotkey taps per speed change")
    ap.add_argument("--startup-wait", type=float, default=5.0)
    ap.add_argument("--key-speed-up", default=None)
    ap.add_argument("--key-speed-down", default=None)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    cfg = Config()
    if args.game_exe:
        cfg.game_exe = args.game_exe
    cfg.replay_path = str(Path(args.replay))
    cfg.events_path = args.events
    cfg.output_path = args.output
    cfg.speed_fast = args.speed_fast
    cfg.map_size = args.map_size
    cfg.startup_wait = args.startup_wait
    if args.minimap:
        parts = [int(p) for p in args.minimap.split(",")]
        if len(parts) != 4:
            ap.error("--minimap must be x,y,w,h")
        cfg.minimap = tuple(parts)  # type: ignore[assignment]
    cfg.zoom_out_clicks = args.zoom_out
    cfg.speed_steps = args.speed_steps
    if args.key_speed_up:
        cfg.key_speed_up = args.key_speed_up
    if args.key_speed_down:
        cfg.key_speed_down = args.key_speed_down
    cfg.debug = args.debug  # type: ignore[attr-defined]
    cfg.resolve()
    run(cfg)


if __name__ == "__main__":
    main()
