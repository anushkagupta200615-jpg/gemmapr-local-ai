import os

import pytest

from app.capture import FakeSource, get_source, session_type


def test_session_type_windows(monkeypatch):
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    assert session_type() == "windows"


def test_session_type_x11(monkeypatch):
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    assert session_type() == "x11"


def test_session_type_wayland(monkeypatch):
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert session_type() == "wayland"


def test_get_source_refuses_wayland(monkeypatch):
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    with pytest.raises(RuntimeError, match="Xorg"):
        get_source()


def test_get_source_needs_display(monkeypatch):
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "tty")
    monkeypatch.delenv("DISPLAY", raising=False)
    with pytest.raises(RuntimeError, match="headless"):
        get_source()


def test_fake_source_scripted_labels_dedupe():
    src = FakeSource(["Google Docs - Essay", "Google Docs - Essay"])
    f1, f2 = src.capture(), src.capture()
    assert f1.label.startswith("Google Docs")
    assert f1.hash == f2.hash  # identical scripted frames dedupe


def test_app_selfcheck_runs_headless(monkeypatch, capsys):
    # full `selfcheck` smoke: db probe + provider parse must not explode
    monkeypatch.setenv("LETCHACK_ALLOW_HEADLESS", "1")
    from app.__main__ import selfcheck

    rc = selfcheck()
    assert rc in (0, 1)  # either fully clean or a listed red flag (missing deps)
