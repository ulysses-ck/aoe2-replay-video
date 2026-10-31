"""Exploratory script: inspect a replay with mgz."""
import os, sys
from mgz.summary import FullSummary

REPLAY = sys.argv[1] if len(sys.argv) > 1 else "/home/ulysses/wks/aoe2-replays/SP Replay v101.103.48987.0 @2026.09.07 114953.aoe2record"

with open(REPLAY, "rb") as f:
    s = FullSummary(f)

print("duration ms:", s.get_duration() if hasattr(s, "get_duration") else "n/a")
print("map:", s.get_map())
print("players:")
for p in s.get_players():
    print(" ", p)
print("num actions:", len(s._actions))
print("first 10 actions:")
for a in s._actions[:10]:
    print(" ", a)
print("action types count:")
from collections import Counter
print(Counter(a[1] for a in s._actions))
