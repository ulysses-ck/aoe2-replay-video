"""CLI entrypoint for control + capture."""
from __future__ import annotations

import argparse
import json
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
    ap.add_argument("--map-size", type=int, default=200)
    ap.add_argument("--minimap", default=None, help="x,y,w,h")
    ap.add_argument("--startup-wait", type=float, default=20.0)
    args = ap.parse_args()

    cfg = Config()
    if args.game_exe:
        cfg.game_exe = args.game_exe
    cfg.replay_path = args.replay
    cfg.events_path = args.events
    cfg.output_path = args.output
    cfg.speed_fast = args.speed_fast
    cfg.map_size = args.map_size
    cfg.startup_wait = args.startup_wait
    if args.minimap:
        parts = [int(p) for p in args.minimap.split(",")]
        cfg.minimap = tuple(parts)  # type: ignore[assignment]
    cfg.resolve()
    run(cfg)


if __name__ == "__main__":
    main()
