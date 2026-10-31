"""Parse an AoE2:DE replay and detect highlight events.

Uses mgz's fast body parser. Header parsing is bypassed (we read the body
offset from the first 4 bytes of the file), so this works across game
versions that mgz's header parser does not yet support.

NOTE: BUILD-based detection (Castle, Monastery, SiegeWorkshop, Wonder, AgeUp)
is disabled for now because building_id parsing is unreliable in game versions
>= 57257 (mgz-fast misreads the BUILD packet). Only sync-based (Raid, Battle)
and action-based (APMPeak) events are emitted.

Camera targets use the event player's most recent action position (where that
player was actually looking/acting), falling back to the recorded player's
VIEWLOCK when no action position is available.
"""
from __future__ import annotations

import io
import json
import struct
import zlib
from collections import defaultdict
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


def get_map_size(replay_path: str) -> int | None:
    """Read the map size (in tiles) from the replay header.

    The header is a raw-deflate compressed blob.  Only the small fixed prefix
    that holds the DE game options is parsed; in modern DE saves the ``diff``
    field stores the map size in tiles (e.g. 144, 200).
    """
    raw = Path(replay_path).read_bytes()
    if len(raw) < 20:
        return None
    header_len = struct.unpack_from("<I", raw, 0)[0]
    if header_len <= 0 or header_len > len(raw):
        return None
    try:
        # header_length (4) + check (4) then a raw-deflate stream
        data = zlib.decompress(raw[8:header_len], wbits=-15)
    except zlib.error:
        return None

    try:
        end = data.index(b"\x00")  # game version CString, e.g. b"VER 9.4"
        p = end + 1
        old_save = struct.unpack_from("<f", data, p)[0]
        p += 4
        if old_save == -1:
            new_save = struct.unpack_from("<I", data, p)[0]
            p += 4
            save_version = new_save / 65536.0
        else:
            save_version = old_save

        def u32() -> int:
            nonlocal p
            value = struct.unpack_from("<I", data, p)[0]
            p += 4
            return value

        u32()  # build
        if save_version >= 26.16:
            u32()  # timestamp
        u32()  # version (float)
        u32()  # interval_version
        u32()  # game_options_version
        dlc_count = u32()
        if dlc_count > 64:
            return None
        for _ in range(dlc_count):
            u32()
        u32()  # dataset_ref
        map_size = u32()  # modern DE: map size in tiles
    except struct.error:
        return None
    return map_size if 50 <= map_size <= 600 else None


def parse_events(replay_path: str) -> list[Event]:
    buf = _body_buffer(replay_path)

    global_view = (0.0, 0.0)
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
            viewlock_history.append((cur_time, float(x), float(y)))
        elif op == fast.Operation.ACTION:
            action_type, ap = payload
            player = ap.get("player_id") if isinstance(ap, dict) else None
            x = ap.get("x") if isinstance(ap, dict) else None
            y = ap.get("y") if isinstance(ap, dict) else None
            if player is not None:
                player_actions[player].append(
                    (cur_time, float(x) if x is not None else None,
                     float(y) if y is not None else None)
                )

    # Nearest recorded-player camera position at or before time ``t``.
    def nearest_view(t: int) -> tuple[float, float]:
        best = global_view
        for vt, vx, vy in viewlock_history:
            if vt <= t:
                best = (vx, vy)
            else:
                break
        return best

    # Nearest action position of a given player at or before ``t``.
    def nearest_action(player: int, t: int, max_age: int = 120_000) -> tuple[float, float] | None:
        for at, ax, ay in reversed(player_actions.get(player, [])):
            if at > t:
                continue
            if t - at > max_age:
                break
            if ax is not None and ay is not None:
                return (ax, ay)
        return None

    # APM peaks: windows with an action count well above recent average.
    WINDOW = 60_000
    for player, acts in player_actions.items():
        if len(acts) < 30:
            continue
        t_min = acts[0][0]
        t_max = acts[-1][0]
        step = 30_000
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
                events.append(Event(t=ts + WINDOW // 2, type="APMPeak", player=player,
                                    x=cx, y=cy, extra={"apm": cnt}))

    # Raids / battles from sync obj_count drops.
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
            while j < n and series[j][0] - t0 <= 30_000:
                if series[j][1] < min_oc:
                    min_oc = series[j][1]
                    min_t = series[j][0]
                j += 1
            drop = oc0 - min_oc
            if drop >= 10:
                kind = "Battle" if drop >= 20 else "Raid"
                pos = nearest_action(player, min_t)
                if pos is None:
                    pos = nearest_view(min_t)
                events.append(Event(t=min_t, type=kind, player=player,
                                    x=pos[0], y=pos[1], extra={"drop": drop}))
                i = j
            else:
                i += 1

    # Deduplicate per (type, player): collapse repeats within 10 s.
    last_seen: dict[tuple[str, int | None], int] = {}
    deduped: list[Event] = []
    for ev in sorted(events, key=lambda e: e.t):
        key = (ev.type, ev.player)
        seen = last_seen.get(key)
        if seen is not None and ev.t - seen < 10_000:
            continue
        last_seen[key] = ev.t
        deduped.append(ev)
    return deduped


def events_to_json(events: Iterable[Event]) -> str:
    return json.dumps([asdict(e) for e in events], indent=2)


if __name__ == "__main__":
    import sys as _sys

    evs = parse_events(_sys.argv[1])
    print(f"parsed {len(evs)} events; map_size={get_map_size(_sys.argv[1])}")
    if len(_sys.argv) > 2:
        Path(_sys.argv[2]).write_text(events_to_json(evs))
        print("saved to", _sys.argv[2])
