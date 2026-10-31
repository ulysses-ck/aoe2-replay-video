# AGENTS.md

Agent instructions for the `aoe2-replay-video` repository.

## Project

Desktop tool that turns an Age of Empires II: DE replay (`.aoe2record`) into a summarized highlight video: accelerates dead time, keeps 1x on key events, centers camera, exports `.mp4`, optionally uploads to YouTube.

- Public repo: https://github.com/ulysses-ck/aoe2-replay-video
- Spec: `SPEC.md`. README has status and usage.

## Stack

- Python 3.10+ (dev on 3.13 via uv).
- Parsing: `mgz` (PyPI) fast body parser. Header parsing is bypassed (body offset read from first 4 bytes).
- GUI (planned): CustomTkinter / PySide6.
- Keyboard/mouse: pyautogui / pynput.
- Video: ffmpeg-python + ffmpeg CLI.
- YouTube: google-api-python-client + google-auth-oauthlib.

## Layout

```
src/aoe2_replay_video/
  parser/replay.py   # Fase 1 done: parse_events()
  control/           # Fase 2 (pending)
  editing/           # Fase 3 (pending)
  youtube/           # Fase 4 (pending)
  ui/                # GUI (pending)
scripts/             # exploration scripts (not shipped)
graphify-out/        # generated knowledge graph (gitignored? check .gitignore)
```

## Commands

```bash
uv venv .venv && uv pip install -e .
PYTHONPATH=src .venv/bin/python -c "from aoe2_replay_video.parser import parse_events; print(len(parse_events('replay.aoe2record')))"
```

## Conventions

- Never commit `.aoe2record`, `.mp4`, tokens, `client_secret*.json`, `recordings/`, `output/` (see `.gitignore`).
- Parser: body-only parsing via offset; do not rely on mgz header parser for new game versions.
- Dev environment details live in ai-memory (not in repo).

## Dev environment (host)

- WSL Debian on Windows host.
- AoE2 DE: `D:\XboxGames\Age of Empires II- Definitive Edition\Content\gamelaunchhelper.exe`
- Replays source: `C:\Users\ulise\Games\Age of Empires 2 DE\2535439686983128\savegame` (copied to `~/wks/aoe2-replays`).
- OBS Studio available on host.

## Current priority

MVP soon. Next: Fase 2 (game control + capture). Refinement of event detection comes later.
