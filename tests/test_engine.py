"""Full-pipeline test: FakeSource → MockProvider → Policy → Store → XP.

This is the tracer bullet from issue #2 — the whole engine working headlessly.
"""

import pytest

from app.capture import FakeSource
from app.classifier import MockProvider
from app.config import Settings
from app.engine import Engine
from app.models import Goal
from app.store import Store


def make_engine(labels, tmp_path, strictness="medium"):
    settings = Settings(strictness=strictness)
    store = Store(tmp_path / "engine.db")
    engine = Engine(settings=settings, store=store, provider=MockProvider())
    engine.enable_watch(FakeSource(labels))
    return engine, store


def test_watch_off_ticks_are_skipped(tmp_path):
    settings = Settings()
    store = Store(tmp_path / "t.db")
    engine = Engine(settings=settings, store=store, provider=MockProvider())
    assert engine.tick(now=1.0) == {"skipped": "watch_off"}


def test_two_drifts_open_gate_medium(tmp_path):
    engine, store = make_engine(
        ["YouTube - Cats", "Reddit - memes", "Reddit - memes"], tmp_path
    )
    d1 = engine.tick(now=100.0)["decision"]
    d2 = engine.tick(now=110.0)["decision"]
    assert d1.action == "hold_silent"
    assert d2.action == "open_gate"
    # decisions persisted for the evidence trail
    rows = store.conn.execute("SELECT action FROM decisions").fetchall()
    assert {"hold_silent", "open_gate"} <= {r["action"] for r in rows}


def test_duplicate_frame_skips_classification(tmp_path):
    engine, _ = make_engine(["Spotify - Chill", "Spotify - Chill"], tmp_path)
    r1 = engine.tick(now=100.0)
    r2 = engine.tick(now=110.0)
    assert "decision" in r1
    assert r2 == {"skipped": "duplicate_frame"}


def test_gate_then_negotiation_then_cooldown(tmp_path):
    engine, store = make_engine(
        ["YouTube - Cats", "YouTube - Shorts"], tmp_path, strictness="hard"
    )
    assert engine.tick(now=100.0)["decision"].action == "open_gate"
    out = engine.negotiate("one quick break please")
    assert out["concede"] is False  # hard mode holds on a break request
    assert out["chore"]  # penalty-zone chore assigned
    assert engine.policy.gate_open is False
    # cooldown: further drift is watched silently until cooldown expires
    assert engine.tick(now=200.0)["decision"].action == "hold_silent"
    assert len(store.negotiations()) == 1
    assert len(store.open_chores()) == 1


def test_medium_concedes_structured_break(tmp_path):
    engine, _ = make_engine(
        ["YouTube - a", "YouTube - b"], tmp_path, strictness="medium"
    )
    engine.tick(now=100.0)
    engine.tick(now=110.0)  # gate open
    out = engine.negotiate("quick coffee break?")
    assert out["concede"] is True
    assert out.get("chore", "") == ""


def test_focus_block_completes_and_awards_xp(tmp_path):
    engine, store = make_engine(
        [
            "VS Code - engine.py",      # on_track: focus block starts
            "Google Docs - Essay",       # on_track continues
            "Spotify - Chill mix",       # break: block ends, award
        ],
        tmp_path,
    )
    store.add_goal("Smoke goal", minutes=0, difficulty="medium")

    events = []
    engine.subscribe(events.append)

    engine.tick(now=100.0)
    engine.tick(now=200.0)
    engine.tick(now=300.0)  # transition → award 25 + streak(1)*2 = 27

    assert store.xp_total() == 27
    assert len(store.goals(include_done=False)) == 0  # goal marked done
    xp_events = [e for e in events if e["type"] == "xp"]
    assert xp_events and xp_events[0]["amount"] == 27
    assert xp_events[0]["level"] == 1


def test_short_focus_block_is_not_rewarded(tmp_path):
    engine, store = make_engine(
        ["VS Code - engine.py", "Spotify - Chill mix"], tmp_path
    )
    store.add_goal("Real goal", minutes=30, difficulty="hard")
    engine.tick(now=100.0)
    engine.tick(now=200.0)  # 100s < 30min
    assert store.xp_total() == 0


def test_capture_outage_does_not_award_xp_for_unobserved_time(tmp_path, monkeypatch):
    """A failed capture bridges unobserved minutes — the focus block must be
    invalidated so the next non-work verdict can't complete a goal with time
    the System never saw."""
    engine, store = make_engine(
        ["VS Code - engine.py", "Spotify - Chill mix"], tmp_path
    )
    store.add_goal("Essay", minutes=1, difficulty="medium")
    engine.tick(now=100.0)  # on_track → focus block starts

    # capture fails once (e.g. display hiccup): unknown gap, then recovers
    real_capture = engine.source.capture

    def flaky(goals=None):
        raise RuntimeError("capture failed")

    monkeypatch.setattr(engine.source, "capture", flaky)
    with pytest.raises(RuntimeError):
        engine.tick(now=190.0)
    engine.note_capture_failure()  # what WatchThread does on failure
    assert engine._on_track_start is None

    # next successful capture is a break: the unseen gap must not earn XP
    monkeypatch.setattr(engine.source, "capture", real_capture)
    engine.tick(now=250.0)
    assert store.xp_total() == 0
    # the goal is NOT completed by unobserved time
    assert len(store.goals(include_done=False)) == 1


def test_note_capture_failure_is_a_noop_without_active_focus(tmp_path):
    engine, _ = make_engine(["VS Code - engine.py"], tmp_path)
    engine._on_track_start = None
    engine.note_capture_failure()
    assert engine._on_track_start is None  # stays None, no crash


def test_verdicts_land_in_store_with_provider_name(tmp_path):
    engine, store = make_engine(["VS Code - main.py"], tmp_path)
    store.add_goal("Essay", minutes=30, difficulty="medium")
    engine.tick(now=10.0)
    v = store.verdicts(limit=1)[0]
    assert v["state"] == "on_track"
    assert v["provider"] == "mock"
    assert v["frame_id"] >= 1


def test_events_carried_to_subscribers(tmp_path):
    settings = Settings()
    store = Store(tmp_path / "t.db")
    engine = Engine(settings=settings, store=store, provider=MockProvider())
    seen = []
    engine.subscribe(seen.append)
    engine.enable_watch(FakeSource(["YouTube - x"]))
    engine.tick(now=1.0)
    types = [e["type"] for e in seen]
    assert "watch" in types and "verdict" in types
