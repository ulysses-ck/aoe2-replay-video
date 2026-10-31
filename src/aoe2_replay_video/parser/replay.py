"""Parse an AoE2:DE replay and detect highlight events.

Uses mgz's fast body parser. Header parsing is bypassed (we read the body
offset from the first 4 bytes of the file), so this works across game
versions that mgz's header parser does not yet support.
"""
from __future__ import annotations

import io
import json
import math
import struct
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import mgz.fast as fast  # noqa: E402  (mgz.fast.operation / meta)


AGE_NAMES = {101: "Feudal", 102: "Castle", 103: "Imperial"}
BUILD_TARGETS = {82: "Castle", 49: "SiegeWorkshop", 276: "Wonder", 104: "Monastery"}


@dataclass
class Event:
    t: int          # milliseconds from game start
    type: str
    player: int | None = None
    x: float | None = None
    y: float | None = None
    extra: dict | None = None


def _body_buffer(path: str) -> io.BytesIO:
    raw = Path(path).read_bytes()
    if len(raw) < 4:
        raise ValueError("replay file too small")
    header_len = struct.unpack("<I", raw[:4])[0]
    if header_len > len(raw):
        raise ValueError("invalid header length in replay")
    buf = io.BytesIO(raw[header_len:])
    fast.meta(buf)
    return buf


def parse_events(replay_path: str) -> list[Event]:
    """Return a time-ordered list of highlight events for a replay."""
    buf = _body_buffer(replay_path)

    player_tc: dict[int, tuple[float, float]] = {}
    global_view = (0.0, 0.0)
    player_actions: dict[int, list[tuple[int, float | None, float | None]]] = defaultdict(list)
    sync_obj: dict[int, list[tuple[int, int]]] = defaultdict(list)
    events: list[Event] = []

    cur_time = 0
    while True:
        try:
            op, payload = fast.operation(buf)
        except EOFError:
            break
        if op == fast.Operation.SYNC:
            inc = payload[0]
            cur_time += inc
            p = payload[2] if (isinstance(payload, tuple) and len(payload) >= 3) else {}
            for pid, info in p.items():
                if pid == "current_time":
                    continue
                try:
                    pid_i = int(pid)
                except (ValueError, TypeError):
                    continue
                oc = info.get("obj_count") if isinstance(info, dict) else None
                if oc is not None:
                    sync_obj[pid_i].append((cur_time, int(oc)))
        elif op == fast.Operation.VIEWLOCK:
            x, y = payload
            global_view = (float(x), float(y))
        elif op == fast.Operation.ACTION:
            action_type, ap = payload
            name = action_type.name
            t = cur_time
            player = ap.get("player_id") if isinstance(ap, dict) else None
            x = ap.get("x") if isinstance(ap, dict) else None
            y = ap.get("y") if isinstance(ap, dict) else None
            if name == "BUILD":
                bid = ap.get("building_id") if isinstance(ap, dict) else None
                if bid == 109 and player is not None and player not in player_tc and x is not None and y is not None:
                    player_tc[player] = (float(x), float(y))
                if bid in BUILD_TARGETS and x is not None and y is not None:
                    kind = BUILD_TARGETS[bid]
                    if kind in ("Castle", "SiegeWorkshop"):
                        for ep, (ex, ey) in player_tc.items():
                            if ep == player:
                                continue
                            if math.hypot(float(x) - ex, float(y) - ey) <= 40:
                                kind = "Advance"
                                break
                    events.append(Event(t=t, type=kind, player=player, x=float(x), y=float(y)))
            elif name == "RESEARCH":
                tid = ap.get("technology_id") if isinstance(ap, dict) else None
                if tid in AGE_NAMES and player is not None:
                    cx, cy = player_tc.get(player, global_view)
                    events.append(Event(t=t, type="AgeUp", player=player, x=cx, y=cy, extra={"age": AGE_NAMES[tid]}))
            elif name == "DROP_RELIC":
                cx, cy = (player_tc.get(player, global_view) if player is not None else global_view)
                events.append(Event(t=t, type="Relic", player=player, x=cx, y=cy))
            if player is not None:
                player_actions[player].append((t, (float(x) if x is not None else None), (float(y) if y is not None else None)))

    # APM peaks
    WINDOW = 60000
    for player, acts in player_actions.items():
        if len(acts) < 30:
            continue
        t_min = acts[0][0]
        t_max = acts[-1][0]
        step = 30000
        win_counts: list[tuple[int, int]] = []
        ts = t_min
        while ts + WINDOW <= t_max:
            cnt = sum(1 for (t, _, _) in acts if ts <= t < ts + WINDOW)
            win_counts.append((ts, cnt))
            ts += step
        for i, (ts, cnt) in enumerate(win_counts):
            prev = [wc for (_, wc) in win_counts[max(0, i - 3):i]]
            mean_prev = (sum(prev) / len(prev)) if prev else 0.0
            if mean_prev > 0 and cnt >= mean_prev * 1.5 and cnt - mean_prev >= 30 and cnt >= 40:
                ws = [a for a in acts if ts <= a[0] < ts + WINDOW and a[1] is not None]
                if ws:
                    cx = sum(a[1] for a in ws) / len(ws)  # type: ignore[arg-type]
                    cy = sum(a[2] for a in ws) / len(ws)  # type: ignore[arg-type]
                else:
                    cx, cy = player_tc.get(player, global_view)
                events.append(Event(t=ts + WINDOW // 2, type="APMPeak", player=player, x=cx, y=cy, extra={"apm": cnt}))

    # Raids / battles from sync obj_count drops
    for player, series in sync_obj.items():
        if len(series) < 5:
            continue
        i = 0
        n = len(series)
        while i < n - 1:
            t0, oc0 = series[i]
            j = i + 1
            min_oc = oc0
            min_t = t0
            while j < n and series[j][0] - t0 <= 30000:
                if series[j][1] < min_oc:
                    min_oc = series[j][1]
                    min_t = series[j][0]
                j += 1
            drop = oc0 - min_oc
            if drop >= 5:
                kind = "Battle" if drop >= 15 else "Raid"
                cx, cy = player_tc.get(player, global_view)
                events.append(Event(t=min_t, type=kind, player=player, x=cx, y=cy, extra={"drop": drop}))
                i = j
            else:
                i += 1

    events.sort(key=lambda e: e.t)
    return events


def events_to_json(events: Iterable[Event]) -> str:
    return json.dumps([asdict(e) for e in events], indent=2)


if __name__ == "__main__":
    import sys as _sys

    evs = parse_events(_sys.argv[1])
    print(f"parsed {len(evs)} events")
    if len(_sys.argv) > 2:
        Path(_sys.argv[2]).write_text(events_to_json(evs))
        print("saved to", _sys.argv[2])
