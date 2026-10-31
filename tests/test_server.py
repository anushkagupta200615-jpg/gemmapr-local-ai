"""Engine-surface smoke tests: pages, state API, negotiation, WS push."""

import pytest
from fastapi.testclient import TestClient

from app.capture import FakeSource
from app.classifier import MockProvider
from app.config import Settings
from app.engine import Engine
from app.server import create_app
from app.store import Store


@pytest.fixture()
def client(tmp_path):
    settings = Settings(screenshot_interval_sec=3600)  # watcher thread stays idle
    store = Store(tmp_path / "t.db")
    engine = Engine(settings=settings, store=store, provider=MockProvider())
    engine.enable_watch(FakeSource(["VS Code - main.py", "YouTube - Cats"]))
    engine.disable_watch()  # source injected; watch OFF for state assertions
    tc = TestClient(create_app(engine))
    tc.engine = engine  # type: ignore[attr-defined]
    tc.store = store  # type: ignore[attr-defined]
    with tc:
        yield tc


def test_pages_serve(client):
    hud = client.get("/")
    assert hud.status_code == 200 and "Goals" in hud.text
    gate = client.get("/gate")
    assert gate.status_code == 200 and "THE GATE" in gate.text
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_state_shape(client):
    s = client.get("/api/state").json()
    for key in (
        "watch_on", "gate_open", "strictness", "xp_total", "level",
        "xp_into_level", "xp_level_size", "focus_streak", "goals",
        "open_chores", "recent_verdicts", "negotiations",
    ):
        assert key in s, key
    assert s["watch_on"] is False
    assert s["strictness"] == "medium"


def test_goals_flow(client):
    r = client.post("/api/goals", json={"title": "Essay", "minutes": 0, "difficulty": "medium"})
    assert r.status_code == 200 and r.json()["goal_id"] >= 1
    titles = [g["title"] for g in client.get("/api/goals").json()["goals"]]
    assert "Essay" in titles
    assert client.post("/api/goals", json={"title": "   "}).status_code == 422


def test_watch_toggle_roundtrip(client):
    on = client.post("/api/watch", json={"on": True}).json()
    assert on["watch"] is True
    assert client.get("/api/state").json()["watch_on"] is True
    off = client.post("/api/watch", json={"on": False}).json()
    assert off["watch"] is False


def test_watch_requires_real_source_when_none_injected(tmp_path):
    engine = Engine(
        settings=Settings(), store=Store(tmp_path / "t.db"), provider=MockProvider()
    )
    with TestClient(create_app(engine)) as tc:
        r = tc.post("/api/watch", json={"on": True})
        assert r.status_code == 400  # headless box has no display: refused loudly


def test_negotiation_via_api(client):
    r = client.post("/api/negotiate", json={"message": "quick coffee break?"})
    body = r.json()
    assert r.status_code == 200
    assert body["concede"] is True  # medium concedes structured breaks
    assert "message" in body


def test_history_and_privacy_switch(client):
    client.store.add_goal("Essay", minutes=0, difficulty="medium")  # enables on_track
    client.engine.enable_watch(client.engine.source)
    client.engine.tick(now=10.0)  # one real observation lands
    client.engine.disable_watch()
    h = client.get("/api/history").json()
    assert len(h["verdicts"]) == 1 and h["verdicts"][0]["state"] == "on_track"
    assert client.post("/api/history/delete").json()["deleted"] is True
    assert client.get("/api/history").json()["verdicts"] == []


def test_ws_pushes_verdict_event(client):
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        client.engine.enable_watch(client.engine.source)
        client.engine.tick(now=5.0)
        client.engine.disable_watch()
        # enable_watch emits a watch event first; drain until the verdict lands
        types = []
        for _ in range(5):
            event = ws.receive_json()
            types.append(event["type"])
            if event["type"] == "verdict":
                break
        assert "verdict" in types


def test_journal_page_and_api(client):
    assert client.get("/journal").status_code == 200
    client.store.add_goal("Essay", minutes=0, difficulty="medium")
    client.engine.enable_watch(client.engine.source)
    client.engine.tick(now=10.0)   # on_track → focus block starts
    client.engine.tick(now=20.0)   # break → block ends → XP awarded
    client.engine.disable_watch()
    client.post("/api/negotiate", json={"message": "quick coffee break?"})
    j = client.get("/api/journal").json()
    kinds = [e["kind"] for e in j["timeline"]]
    assert "verdict" in kinds and "negotiation" in kinds and "xp" in kinds
    # newest first
    ts_list = [e["ts"] for e in j["timeline"]]
    assert ts_list == sorted(ts_list, reverse=True)


def test_journal_empty_is_honest(client):
    j = client.get("/api/journal").json()
    assert j["timeline"] == [] and j["total_xp"] == 0


def test_goal_minutes_validation(client):
    # non-numeric minutes -> 422 validation error, not a crashing 500
    r = client.post("/api/goals", json={"title": "Essay", "minutes": "abc", "difficulty": "medium"})
    assert r.status_code == 422
    r = client.post("/api/goals", json={"title": "Essay", "minutes": True})
    assert r.status_code == 422
    # a valid ZERO-minute goal stays zero (no `or 30` coercion)
    client.post("/api/goals", json={"title": "Zero-Sprint", "minutes": 0, "difficulty": "medium"})
    zero = [g for g in client.get("/api/goals").json()["goals"] if g["title"] == "Zero-Sprint"]
    assert zero and zero[0]["minutes"] == 0


def test_watch_toggle_string_false_is_off(client):
    # strict boolean contract: the string "false" must not switch watching on
    r = client.post("/api/watch", json={"on": "false"})
    assert r.json()["watch"] is False
    assert client.get("/api/state").json()["watch_on"] is False


def test_boot_with_watch_enabled_starts_watcher(tmp_path):
    """LETCHACK_WATCH=1 flow: engine pre-enabled at boot -> the watcher must
    actually run, not just display 'Stop watching' while nothing captures."""
    import time as _time

    store = Store(tmp_path / "w.db")
    engine = Engine(
        settings=Settings(screenshot_interval_sec=0.5, dedupe_frames=False),
        store=store,
        provider=MockProvider(),
    )
    engine.enable_watch(FakeSource(["VS Code - a.py"]))
    events: list = []
    engine.subscribe(events.append)
    with TestClient(create_app(engine)) as tc:
        _time.sleep(2.6)  # first watcher tick lands at ~2s
    # at least one real verdict event came from the background watcher
    assert any(e.get("type") == "verdict" for e in events)
