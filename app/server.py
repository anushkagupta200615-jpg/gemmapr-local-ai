"""HTTP/WS surface. The engine serves ONE static page on localhost — no
build tooling, no CDN assets (kiosk-safe offline). Tauri (PR-4) wraps
`/` as the HUD and `/gate` as the always-on-top gate window.

Endpoints:
    GET  /               HUD page
    GET  /gate           fullscreen gate overlay (negotiation)
    GET  /api/state       live snapshot (watch, xp, level, verdicts, goals)
    GET  /api/goals
    POST /api/goals       {title, minutes, difficulty}
    POST /api/watch       {on: true|false} — explicit opt-in consent
    POST /api/negotiate   {message} → {concede, message, chore?}
    GET  /api/history     evidence trail (verdicts + decisions)
    POST /api/history/delete  wipe all observations (privacy premise)
    WS   /ws              engine event bus (verdict/xp/negotiation/watch)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import threading
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .engine import Engine, WatchThread

WEB_DIR = Path(__file__).parent / "web"


def create_app(engine: Engine) -> FastAPI:
    state: dict[str, Any] = {"watcher": None, "loop": None}
    queues: list[asyncio.Queue] = []
    queues_lock = threading.Lock()

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        state["loop"] = asyncio.get_running_loop()
        # LETCHACK_WATCH=1 (or a prior enable): the watcher must actually run,
        # not just report Stop-watching in the HUD.
        if engine.watch_on and state["watcher"] is None:
            _start_watcher()
        yield
        _stop_watcher()

    app = FastAPI(title="Let'shack Bouncer", version="0.2.0", lifespan=_lifespan)
    state: dict[str, Any] = {"watcher": None, "loop": None}
    queues: list[asyncio.Queue] = []
    queues_lock = threading.Lock()

    def _broadcast(event: dict[str, Any]) -> None:
        """Engine callbacks run on the WatchThread; hop into the loop."""
        loop = state["loop"]
        if loop is None:
            return
        with queues_lock:
            targets = list(queues)
        for q in targets:
            loop.call_soon_threadsafe(q.put_nowait, event)

    engine.subscribe(_broadcast)

    # ---- pages ----

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/gate")
    def gate() -> FileResponse:
        return FileResponse(WEB_DIR / "gate.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    # ---- state ----

    @app.get("/api/state")
    def api_state() -> dict[str, Any]:
        from .xp import level_for, progress_in_level

        total = engine.store.xp_total()
        into, need = progress_in_level(total)
        return {
            "watch_on": engine.watch_on,
            "gate_open": engine.policy.gate_open,
            "strictness": engine.policy.strictness,
            "xp_total": total,
            "level": level_for(total),
            "xp_into_level": into,
            "xp_level_size": need,
            "focus_streak": engine._focus_streak,
            "goals": engine.store.goals(),
            "open_chores": engine.store.open_chores(),
            "recent_verdicts": engine.store.verdicts(limit=8),
            "negotiations": engine.store.negotiations(limit=5),
        }

    @app.get("/api/goals")
    def api_goals() -> dict[str, Any]:
        return {"goals": engine.store.goals()}

    @app.post("/api/goals")
    def api_add_goal(body: dict[str, Any]) -> dict[str, Any]:
        title = str(body.get("title", "")).strip()
        if not title:
            raise HTTPException(422, "goal title required")
        raw_minutes = body.get("minutes", 30)
        # typed: rejects "abc" with 422 (not a 500 crash) and preserves a
        # valid zero-minute demo goal (no `or 30` coercion)
        if isinstance(raw_minutes, bool) or not isinstance(raw_minutes, (int, float)):
            raise HTTPException(422, "minutes must be a number")
        minutes = int(raw_minutes)
        difficulty = str(body.get("difficulty", "easy")).lower()
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "easy"
        gid = engine.store.add_goal(title, minutes=max(0, minutes), difficulty=difficulty)
        return {"goal_id": gid}

    # ---- watch toggle (premise 4: explicit opt-in, deletable) ----

    def _start_watcher() -> None:
        interval = max(2.0, engine.settings.screenshot_interval_sec)
        state["watcher"] = WatchThread(engine, interval)
        state["watcher"].start()

    def _stop_watcher() -> None:
        w: WatchThread | None = state["watcher"]
        if w is not None:
            w.stop()
            state["watcher"] = None

    @app.post("/api/watch")
    def api_watch(body: dict[str, Any]) -> dict[str, Any]:
        # strict boolean: the string "false" must not switch watching on
        on = body.get("on", False) is True
        if on:
            if engine.source is None:
                # real capture only; raises with fix instructions on Wayland
                from .capture import get_source

                try:
                    source = get_source()
                except RuntimeError as exc:
                    raise HTTPException(400, str(exc))
                engine.enable_watch(source)
            else:
                engine.enable_watch(engine.source)  # injected FakeSource (tests)
            _start_watcher()
            return {"watch": True, "note": "frames stay local; delete anytime"}
        engine.disable_watch()
        _stop_watcher()
        return {"watch": False}

    # ---- negotiation (the gate's core moment) ----

    @app.post("/api/negotiate")
    def api_negotiate(body: dict[str, Any]) -> dict[str, Any]:
        message = str(body.get("message", "")).strip()
        if not message:
            raise HTTPException(422, "message required")
        history = body.get("history") or None
        return engine.negotiate(message, history=history)

    @app.get("/history/journal")
    @app.get("/journal")
    def journal() -> FileResponse:
        return FileResponse(WEB_DIR / "journal.html")

    # ---- evidence trail + privacy switch ----

    @app.get("/api/journal")
    def api_journal() -> dict[str, Any]:
        """The attention story, one timeline: verdicts, gate moments,
        negotiations, XP awards, chores — merged and time-sorted."""
        items: list[dict[str, Any]] = []
        for v in engine.store.verdicts(limit=200):
            items.append(
                {
                    "ts": v["ts"],
                    "kind": "verdict",
                    "headline": {
                        "on_track": "🎯 focused",
                        "drift": "🌀 drifted",
                        "break": "☕ break",
                        "unknown": "❔ unclear",
                    }.get(v["state"], v["state"]),
                    "detail": f"{v['summary'] or '—'} ({v['category'] or 'other'})",
                    "state": v["state"],
                }
            )
        for n in engine.store.negotiations(limit=50):
            items.append(
                {
                    "ts": n["ts"],
                    "kind": "negotiation",
                    "headline": "🚪 you said"
                    if not n["conceded"]
                    else "🫱 you argued",
                    "detail": f"“{n['user']}” → "
                    + ("released" if n["conceded"] else "held + chore")
                    + (f" · chore: {n['chore']}" if n["chore"] else ""),
                }
            )
        for x in engine.store.conn.execute(
            "SELECT ts, amount, reason FROM xp ORDER BY xp_id DESC LIMIT 50"
        ):
            items.append(
                {
                    "ts": x["ts"],
                    "kind": "xp",
                    "headline": f"⭐ +{x['amount']} XP",
                    "detail": x["reason"],
                }
            )
        items.sort(key=lambda e: e["ts"], reverse=True)
        return {"timeline": items, "total_xp": engine.store.xp_total()}

    @app.get("/api/history")
    def api_history() -> dict[str, Any]:
        return {
            "verdicts": engine.store.verdicts(limit=50),
            "decisions": [
                dict(r) for r in engine.store.conn.execute(
                    "SELECT * FROM decisions ORDER BY decision_id DESC LIMIT 50"
                )
            ],
            "negotiations": engine.store.negotiations(limit=20),
            "xp": [
                dict(r) for r in engine.store.conn.execute(
                    "SELECT * FROM xp ORDER BY xp_id DESC LIMIT 50"
                )
            ],
        }

    @app.post("/api/history/delete")
    def api_delete_history() -> dict[str, Any]:
        engine.store.delete_all_history()
        return {"deleted": True, "note": "observations wiped; goals kept"}

    # ---- WS event bus ----

    @app.websocket("/ws")
    async def ws_events(ws: WebSocket) -> AsyncIterator[None]:
        await ws.accept()
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        with queues_lock:
            queues.append(q)
        try:
            await ws.send_json({"type": "hello", "watch_on": engine.watch_on})
            while True:
                event = await q.get()
                await ws.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            with queues_lock:
                if q in queues:
                    queues.remove(q)

    return app


def serve(engine: Engine) -> None:  # pragma: no cover - manual run helper
    import uvicorn

    uvicorn.run(
        create_app(engine),
        host=engine.settings.host,
        port=engine.settings.port,
        log_level="warning",
    )
