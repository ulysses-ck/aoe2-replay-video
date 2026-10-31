"""Window management for the game."""
from __future__ import annotations

import sys
import time
from typing import Any


def find_window(title_substring: str = "Age of Empires", timeout: float = 30.0) -> Any:
    """Return a window handle/object matching the title. Cross-platform best effort."""
    deadline = time.time() + timeout
    if sys.platform == "win32":
        try:
            import pygetwindow as gw  # type: ignore

            while time.time() < deadline:
                wins = [w for w in gw.getAllWindows() if title_substring.lower() in (w.title or "").lower()]
                if wins:
                    return wins[0]
                time.sleep(1.0)
        except Exception:
            pass
        try:
            import win32gui  # type: ignore

            def cb(hwnd, acc):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if title_substring.lower() in t.lower():
                        acc.append(hwnd)
                return True

            while time.time() < deadline:
                acc: list[int] = []
                win32gui.EnumWindows(cb, acc)
                if acc:
                    return acc[0]
                time.sleep(1.0)
        except Exception:
            pass
    else:
        # Linux: try wmctrl / xdotool via subprocess
        import subprocess

        while time.time() < deadline:
            try:
                out = subprocess.check_output(["wmctrl", "-l"], text=True, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    if title_substring.lower() in line.lower():
                        return line.split()[0]
            except Exception:
                pass
            try:
                out = subprocess.check_output(["xdotool", "search", "--name", title_substring], text=True, stderr=subprocess.DEVNULL)
                if out.strip():
                    return out.strip().split()[0]
            except Exception:
                pass
            time.sleep(1.0)
    return None


def activate(window: Any) -> None:
    if window is None:
        return
    try:
        if hasattr(window, "activate"):
            window.activate()
            return
    except Exception:
        pass
    if isinstance(window, str):
        try:
            import subprocess

            subprocess.run(["xdotool", "windowactivate", window], check=False, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def _hwnd(window: Any) -> int | None:
    """Best-effort native handle for a window object."""
    if window is None:
        return None
    if isinstance(window, int):
        return window
    return getattr(window, "_hWnd", None)


def maximize(window: Any) -> None:
    """Maximize the window instead of resizing it (keeps the native UI scale)."""
    if window is None:
        return
    if sys.platform == "win32":
        hwnd = _hwnd(window)
        if hwnd:
            try:
                import ctypes

                ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                return
            except Exception:
                pass
    try:
        if hasattr(window, "maximize"):
            window.maximize()
            return
    except Exception:
        pass


def set_geometry(window: Any, x: int, y: int, w: int, h: int) -> None:
    if window is None:
        return
    try:
        if hasattr(window, "moveTo"):
            window.moveTo(x, y)
            window.resizeTo(w, h)
            return
    except Exception:
        pass
    import subprocess, sys

    if sys.platform == "linux":
        try:
            subprocess.run(["wmctrl", "-i", "-r", str(window), "-e", f"0,{x},{y},{w},{h}"], check=False)
        except Exception:
            pass


def get_bbox(window: Any) -> tuple[int, int, int, int] | None:
    """Return (left, top, width, height) of the client area in screen pixels."""
    if window is None:
        return None
    if sys.platform == "win32":
        hwnd = _hwnd(window)
        if hwnd:
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                rect = wintypes.RECT()
                if user32.GetClientRect(hwnd, ctypes.byref(rect)):
                    origin = wintypes.POINT(0, 0)
                    user32.ClientToScreen(hwnd, ctypes.byref(origin))
                    width = rect.right - rect.left
                    height = rect.bottom - rect.top
                    if width > 0 and height > 0:
                        return (origin.x, origin.y, width, height)
            except Exception:
                pass
    try:
        if hasattr(window, "left"):
            return (int(window.left), int(window.top), int(window.width), int(window.height))
    except Exception:
        pass
    if isinstance(window, str):
        try:
            import subprocess

            out = subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", window], text=True, stderr=subprocess.DEVNULL)
            vals = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    vals[k] = int(v)
            if "X" in vals and "Y" in vals and "WIDTH" in vals and "HEIGHT" in vals:
                return (vals["X"], vals["Y"], vals["WIDTH"], vals["HEIGHT"])
        except Exception:
            pass
    return None
