"""Detect highlight events from a replay body (mgz-fast)."""
import io, struct, sys, json, math
from collections import defaultdict, deque
sys.path.insert(0, '/tmp/opencode/mgz-aoeinsights')
from mgz import fast

REPLAY = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None

raw = open(REPLAY, "rb").read()
header_len = struct.unpack('<I', raw[:4])[0]
buf = io.BytesIO(raw[header_len:])
fast.meta(buf)

# State
player_tc = {}          # player -> (x,y) first TC
player_last_view = {}   # player -> (x,y) last viewlock (not tracked per-player; global viewlock)
global_view = (0.0, 0.0)
player_actions = defaultdict(list)   # player -> list of (t, x, y)
sync_obj = defaultdict(list)          # player -> list of (t, obj_count)
all_actions = []                     # (t, player, type, x, y)
age_names = {101: "Feudal", 102: "Castle", 103: "Imperial"}
BUILD_TARGETS = {82: "Castle", 49: "SiegeWorkshop", 276: "Wonder", 104: "Monastery"}

events = []

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
            oc = info.get("obj_count")
            if oc is not None:
                sync_obj[pid_i].append((cur_time, oc))
    elif op == fast.Operation.VIEWLOCK:
        x, y = payload
        global_view = (x, y)
    elif op == fast.Operation.ACTION:
        action_type, ap = payload
        at_name = action_type.name
        t = cur_time
        # extract player and coords
        player = ap.get("player_id") if isinstance(ap, dict) else None
        x = ap.get("x") if isinstance(ap, dict) else None
        y = ap.get("y") if isinstance(ap, dict) else None
        # BUILD
        if at_name == "BUILD":
            bid = ap.get("building_id")
            if bid == 109 and player is not None and player not in player_tc:
                if x is not None and y is not None:
                    player_tc[player] = (x, y)
            if bid in BUILD_TARGETS and x is not None and y is not None:
                # avanzada: if Castle/Siege and enemy TC within 40 tiles
                kind = BUILD_TARGETS[bid]
                if kind in ("Castle", "SiegeWorkshop"):
                    # check enemy TC proximity
                    for ep, (ex, ey) in player_tc.items():
                        if ep == player:
                            continue
                        dist = math.hypot(x - ex, y - ey)
                        if dist <= 40:
                            kind = "Advance"  # asedio
                            break
                events.append({"t": t, "type": kind, "player": player, "x": x, "y": y})
        # RESEARCH age up
        elif at_name == "RESEARCH":
            tid = ap.get("technology_id")
            if tid in age_names and player is not None:
                cx, cy = player_tc.get(player, global_view)
                events.append({"t": t, "type": "AgeUp", "age": age_names[tid], "player": player, "x": cx, "y": cy})
        # DROP_RELIC
        elif at_name == "DROP_RELIC":
            player = ap.get("player_id") if isinstance(ap, dict) else player
            cx, cy = player_tc.get(player, global_view) if player is not None else global_view
            events.append({"t": t, "type": "Relic", "player": player, "x": cx, "y": cy})
        # track actions for APM
        if player is not None:
            player_actions[player].append((t, x, y))
            all_actions.append((t, player, at_name, x, y))

# APM peaks: per player, 60s windows
WINDOW = 60000
for player, acts in player_actions.items():
    if len(acts) < 30:
        continue
    # bin into windows
    if not acts:
        continue
    t_min = acts[0][0]
    t_max = acts[-1][0]
    # sliding window step 30s
    step = 30000
    win_counts = []
    ts = t_min
    while ts + WINDOW <= t_max:
        cnt = sum(1 for (t, _, _) in acts if ts <= t < ts + WINDOW)
        win_counts.append((ts, cnt))
        ts += step
    if not win_counts:
        continue
    # rolling mean of previous 3 windows
    for i, (ts, cnt) in enumerate(win_counts):
        prev = [wc for (wts, wc) in win_counts[max(0, i-3):i]]
        mean_prev = (sum(prev) / len(prev)) if prev else 0
        if mean_prev > 0 and cnt >= mean_prev * 1.5 and cnt - mean_prev >= 30 and cnt >= 40:
            # find centroid of actions in window
            ws = [a for a in acts if ts <= a[0] < ts + WINDOW and a[1] is not None]
            if ws:
                cx = sum(a[1] for a in ws) / len(ws)
                cy = sum(a[2] for a in ws) / len(ws)
            else:
                cx, cy = player_tc.get(player, global_view)
            events.append({"t": ts + WINDOW // 2, "type": "APMPeak", "player": player, "x": cx, "y": cy, "apm": cnt})

# Raids/battles: per player obj_count drops
for player, series in sync_obj.items():
    if len(series) < 5:
        continue
    # detect drops >= 5 within 30s
    # iterate
    i = 0
    n = len(series)
    while i < n - 1:
        t0, oc0 = series[i]
        # find max drop within next 30s
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
            # camera: player base or global
            cx, cy = player_tc.get(player, global_view)
            events.append({"t": min_t, "type": kind, "player": player, "x": cx, "y": cy, "drop": drop})
            # skip ahead
            i = j
        else:
            i += 1

# Sort by time
events.sort(key=lambda e: e["t"])

# Merge nearby events (gap <= 3s) into segments later; here just print count
print("total events:", len(events))
from collections import Counter
print("by type:", Counter(e["type"] for e in events))

if OUT:
    with open(OUT, "w") as f:
        json.dump(events, f, indent=2)
    print("saved to", OUT)
