"""Console safety: diagnostics must never die on a cp1252/cp936 console
(Windows default), where the unicode arrows/emoji in our prints raise
UnicodeEncodeError. _force_utf8_console() reconfigures such streams."""

import sys

from app.__main__ import _force_utf8_console


class FakeStream:
    def __init__(self, encoding: str | None):
        self.encoding = encoding
        self.reconfigured: dict | None = None

    def reconfigure(self, **kw) -> None:
        self.reconfigured = kw


class DumbStream:
    """No reconfigure attribute at all (e.g. pytest capture wrappers)."""

    encoding = "cp1252"


def test_reconfigures_non_utf8_streams(monkeypatch):
    out, err = FakeStream("cp1252"), FakeStream("cp936")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    _force_utf8_console()
    assert out.reconfigured == {"encoding": "utf-8", "errors": "replace"}
    assert err.reconfigured == {"encoding": "utf-8", "errors": "replace"}


def test_leaves_utf8_streams_alone(monkeypatch):
    out = FakeStream("utf-8")
    monkeypatch.setattr(sys, "stdout", out)
    _force_utf8_console()
    assert out.reconfigured is None


def test_survives_streams_without_reconfigure(monkeypatch):
    monkeypatch.setattr(sys, "stdout", DumbStream())
    monkeypatch.setattr(sys, "stderr", None)
    _force_utf8_console()  # must not raise
