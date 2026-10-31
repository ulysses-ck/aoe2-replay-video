"""Parse an AoE2:DE replay and detect highlight events.

Uses mgz's fast body parser. Header parsing is bypassed (we read the body
offset from the first 4 bytes of the file), so this works across game
versions that mgz's header parser does not yet support.

NOTE: BUILD-based detection (Castle, Monastery, SiegeWorkshop, Wonder, AgeUp)
is disabled for now because building_id parsing is unreliable in game versions
>= 57257 (mgz-fast misreads the BUILD packet). Only sync-based (Raid, Battle)
and action-based (APMPeak) events are emitted. Camera targets use the most
recent VIEWLOCK position.
"""
from __future__ import annotations

import io
import json
import math
import struct
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import mgz.fast as fast


@dataclass
class Event:
    t: int
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
    buf = _body_buffer(replay_path)

    global_view = (0.0, 0.0)
    last_viewlock = (0.0, 0.0)
    viewlock_history: list[tuple[int, float, float]] = []
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
            last_viewlock = (float(x), float(y))
            viewlock_history.append((cur_time, float(x), float(y)))
        elif op == fast.Operation.ACTION:
            action_type, ap = payload
            name = action_type.name
            t = cur_time
            player = ap.get("player_id") if isinstance(ap, dict) else None
            x = ap.get("x") if isinstance(ap, dict) else None
            y = ap.get("y") if isinstance(ap, dict) else None
            if player is not None:
                player_actions[player].append(
                    (t, float(x) if x is not None else None, float(y) if y is not None else None)
                )

    # Helper: nearest viewlock before time t
    def nearest_view(t: int) -> tuple[float, float]:
        best = (0.0, 0.0)
        for vt, vx, vy in viewlock_history:
            if vt <= t:
                best = (vx, vy)
            else:
                break
        return best if viewlock_history else global_view

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
                    cx = sum(a[1] for a in ws) / len(ws)
                    cy = sum(a[2] for a in ws) / len(ws)
                else:
                    cx, cy = nearest_view(ts)
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
            if drop >= 10:
                kind = "Battle" if drop >= 20 else "Raid"
                cx, cy = nearest_view(min_t)
                events.append(Event(t=min_t, type=kind, player=player, x=cx, y=cy, extra={"drop": drop}))
                i = j
            else:
                i += 1

    # Deduplicate: same type+player within 10s -> keep first (per player)
    deduped: list[Event] = []
    for ev in sorted(events, key=lambda e: e.t):
        if deduped:
            last = deduped[-1]
            if last.type == ev.type and last.player == ev.player and (ev.t - last.t) < 10000:
                continue
        deduped.append(ev)
    deduped.sort(key=lambda e: e.t)
    return deduped


def events_to_json(events: Iterable[Event]) -> str:
    return json.dumps([asdict(e) for e in events], indent=2)


if __name__ == "__main__":
    import sys as _sys

    evs = parse_events(_sys.argv[1])
    print(f"parsed {len(evs)} events")
    if len(_sys.argv) > 2:
        Path(_sys.argv[2]).write_text(events_to_json(evs))
        print("saved to", _sys.argv[2])
