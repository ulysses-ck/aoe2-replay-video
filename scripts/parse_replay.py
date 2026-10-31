"""Parse a replay with mgz-fast and summarize events."""
import sys, json, io
from collections import Counter
from mgz import fast
from mgz.fast import header as fast_header

REPLAY = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else None

raw = open(REPLAY, "rb").read()
buf = io.BytesIO(raw)

header = fast_header.parse(buf)
print("header parsed; body pos:", buf.tell(), "players:", len(header.get("players", [])))
fast.meta(buf)

BUILD_TARGETS = {82: "Castle", 49: "SiegeWorkshop", 276: "Wonder", 109: "TownCenter", 104: "Monastery"}

timeline = []
cur_time = 0
n = 0
while True:
    try:
        op, payload = fast.operation(buf)
    except EOFError:
        break
    if op == fast.Operation.SYNC:
        inc = payload[0]
        cur_time += inc
        p = payload[2] if (isinstance(payload, tuple) and len(payload) >= 3) else {}
        timeline.append((cur_time, "SYNC", {"players": {k: v for k, v in p.items() if k != "current_time"}}))
    elif op == fast.Operation.ACTION:
        action_type, action_payload = payload
        timeline.append((cur_time, "ACTION", {"type": action_type.name, "payload": action_payload}))
    elif op == fast.Operation.VIEWLOCK:
        x, y = payload
        timeline.append((cur_time, "VIEWLOCK", {"x": x, "y": y}))
    n += 1

print("total ops:", n)
print("actions:", len([t for t in timeline if t[1] == "ACTION"]))
print("syncs:", len([t for t in timeline if t[1] == "SYNC"]))
print("viewlocks:", len([t for t in timeline if t[1] == "VIEWLOCK"]))

c = Counter(t[2]["type"] for t in timeline if t[1] == "ACTION")
print("action type counts:", c.most_common(20))

print("\nRESEARCH events:")
for time_ms, kind, d in timeline:
    if kind == "ACTION" and d["type"] == "RESEARCH":
        p = d["payload"]
        print(f"  t={time_ms}ms tech={p.get('technology_id')} player={p.get('player_id')}")

print("\nBUILD events (target buildings):")
for time_ms, kind, d in timeline:
    if kind == "ACTION" and d["type"] == "BUILD":
        p = d["payload"]
        bid = p.get("building_id")
        if bid in BUILD_TARGETS:
            print(f"  t={time_ms}ms building={BUILD_TARGETS[bid]}({bid}) player={p.get('player_id')} x={p.get('x'):.1f} y={p.get('y'):.1f}")

print("\nDROP_RELIC events:")
for time_ms, kind, d in timeline:
    if kind == "ACTION" and d["type"] == "DROP_RELIC":
        print(f"  t={time_ms}ms payload={d['payload']}")

print("\nSync player obj_count samples (first 3 syncs with players):")
cnt = 0
for time_ms, kind, d in timeline:
    if kind == "SYNC" and d["players"]:
        for pid, info in d["players"].items():
            print(f"  t={time_ms}ms player={pid} obj_count={info.get('obj_count')} dp_obj={info.get('dp_obj_count')} total_res={info.get('total_res')}")
        cnt += 1
        if cnt >= 3:
            break

if out_path:
    with open(out_path, "w") as f:
        json.dump([{"t": t, "kind": k, "data": d} for t, k, d in timeline], f)
    print("\nsaved timeline to", out_path)
