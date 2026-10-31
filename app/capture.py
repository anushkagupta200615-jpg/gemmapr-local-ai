"""Capture layer: produces Frame objects.

One abstraction (`FrameSource`), three implementations:
- `MssSource`: real screen capture via mss. Works on X11 (Linux) and Windows.
  Wayland is refused with instructions (portals make silent capture awful).
- `FakeSource`: scripted frames for tests and the selfcheck smoke run.
- `get_source()`: platform-aware factory used everywhere at runtime.
"""

from __future__ import annotations

import base64
import io
import os
import platform
import zlib

from .models import Frame, Goal

# a valid 1x1 transparent PNG, constant across runs so FakeSource frames
# dedupe deterministically in tests
_FAKE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class FrameSource:
    """Protocol: return the most recent screen observation."""

    def capture(self, goals: list[Goal] | None = None) -> Frame:  # pragma: no cover
        raise NotImplementedError


def session_type() -> str:
    """Return one of: 'windows', 'x11', 'wayland', 'other'."""
    if platform.system() == "Windows":
        return "windows"
    st = (os.environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    if st in ("x11", "wayland"):
        return st
    # fall back to the X display presence: a DISPLAY usually means X11-like
    return "x11" if os.environ.get("DISPLAY") else "other"


class MssSource(FrameSource):
    """Real capture via mss. Lazy-imports so the module is safe headless."""

    def __init__(self, monitor: int = 0, max_width: int = 1024, quality: int = 70):
        self.monitor = monitor
        self.max_width = max_width
        self.quality = quality
        import mss  # required only when actually capturing

        self._mss = mss.mss()
        self._last_hash = ""

    def capture(self, goals: list[Goal] | None = None) -> Frame:
        from PIL import Image

        shot = self._mss.grab(self._mss.monitors[self.monitor + 1])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        if img.width > self.max_width:
            img = img.resize(
                (self.max_width, int(img.height * self.max_width / img.width))
            )
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self.quality)
        frame = Frame(
            image_b64=base64.b64encode(buf.getvalue()).decode(),
            label=active_window_title() or "",
            width=img.width,
            height=img.height,
        )
        self._last_hash = frame.hash
        return frame


def active_window_title() -> str:
    """Best-effort active window title (used as a cheap extra signal).

    - Windows: PowerShell Win32 call
    - X11: xdotool if installed
    - otherwise: empty string; capture still works without it
    """
    try:
        if platform.system() == "Windows":
            import subprocess

            script = (
                "Add-Type -AssemblyName System;"
                "$s=Get-Process | Where-Object{$_.MainWindowTitle} | "
                "Select-Object -First 1 -ExpandProperty MainWindowTitle;"
                "[Console]::Out.Write($s)"
            )
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return out.stdout.strip()[:120] if out.returncode == 0 else ""
        if platform.system() == "Linux" and os.environ.get("DISPLAY"):
            import subprocess

            out = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return out.stdout.strip()[:120] if out.returncode == 0 else ""
    except Exception:
        return ""
    return ""


class FakeSource(FrameSource):
    """Scripted frames for tests and `selfcheck`. NOT a demo mode: the real
    product always captures (premise: real pipeline only)."""

    def __init__(self, labels: list[str]):
        self.labels = list(labels)
        self._i = 0

    def capture(self, goals: list[Goal] | None = None) -> Frame:
        label = self.labels[min(self._i, len(self.labels) - 1)]
        self._i += 1
        # vary one byte per label so distinct scripted frames hash differently
        # (identical labels still produce identical bytes → dedupe applies)
        raw = _FAKE_PNG[:-1] + bytes([zlib.crc32(label.encode()) & 0xFF])
        return Frame(image_b64=base64.b64encode(raw).decode(), label=label)


def get_source() -> FrameSource:
    """Runtime factory. Refuses Wayland loudly and helpfully."""
    st = session_type()
    if st == "wayland":
        raise RuntimeError(
            "Wayland session detected. Silent screen capture needs an Xorg session. "
            "Fix: log out, pick 'Xorg/X11' in the login-screen session gear, log in, "
            f"verify with `echo $XDG_SESSION_TYPE` (want: x11). Windows is unaffected."
        )
    if st == "other" and os.environ.get("LETCHACK_ALLOW_HEADLESS") != "1":
        raise RuntimeError(
            "No X11 display found (are you on a headless box?). "
            "This app captures on a desktop session: X11 Linux or Windows."
        )
    return MssSource()
