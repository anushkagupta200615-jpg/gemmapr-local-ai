"""Engine: wires capture → classify → policy → store → events, with
headless-friendly seams everywhere (clock, source, provider injected).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from .classifier import VerdictProvider
from .config import Settings
from .models import ACTIONS, Classification, Decision, Frame, Goal
from .policy import DEFAULT_COOLDOWN_SEC, Policy
from .store import Store
from .xp import award_for, level_for

EventCallback = Callable[[dict[str, Any]], None]


class Engine:
    """Headless brain. The surface layer (server/UI) subscribes to events."""

    def __init__(
        self,
        settings: Settings,
        store: Store,
        provider: VerdictProvider,
        source: Any | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.settings = settings
        self.store = store
        self.provider = provider
        self.source = source  # FrameSource; None until watch is enabled
        self.clock = clock
        self.policy = Policy(
            strictness=settings.normalised_strictness(),
            cooldown_sec=DEFAULT_COOLDOWN_SEC,
        )
        self.watch_on = False
        self.last_frame_hash = ""
        self.pending_frames: list[Frame] = []
        self._on_track_start: float | None = None
        self._focus_streak = 0
        self._subscribers: list[EventCallback] = []

    # -- subscription (server/UI hooks in here) --

    def subscribe(self, cb: EventCallback) -> None:
        self._subscribers.append(cb)

    def _emit(self, event: dict[str, Any]) -> None:
        for cb in self._subscribers:
            cb(event)

    # -- watch control --

    def enable_watch(self, source: Any) -> dict[str, Any]:
        """Explicit opt-in (premise 4)."""
        self.source = source
        self.watch_on = True
        self._emit({"type": "watch", "on": True})
        return {"watch": True}

    def disable_watch(self) -> dict[str, Any]:
        self.watch_on = False
        self._on_track_start = None
        self._emit({"type": "watch", "on": False})
        return {"watch": False}

    def note_capture_failure(self) -> None:
        """A failed capture period is UNOBSERVED time — it must never count
        as focus. Invalidate the running focus block so a later verdict
        cannot award XP for the gap the System never saw."""
        self._on_track_start = None

    # -- one capture+classify cycle --

    def tick(self, now: float | None = None) -> dict[str, Any]:
        now = self.clock() if now is None else now
        if not self.watch_on or self.source is None:
            return {"skipped": "watch_off"}

        frame: Frame = self.source.capture()
        title_hash = frame.hash
        store_fresh = not (
            self.settings.dedupe_frames and title_hash == self.last_frame_hash
        )
        frame_id = self.store.add_frame(frame.ts, frame.label, title_hash)
        self.last_frame_hash = title_hash
        if not store_fresh:
            return {"skipped": "duplicate_frame"}

        classification = self.provider.classify_frames([frame], self._goals())[-1]
        self.store.add_verdict(
            frame_id,
            frame.ts,
            classification.state,
            classification.summary,
            classification.confidence,
            classification.category,
            getattr(self.provider, "name", "unknown-provider"),
        )
        decision = self.policy.decide(classification, now=now)
        self.store.add_decision(now, decision.action, decision.message, decision.xp_awarded)
        xp = self._track_focus(classification, now)
        event = {
            "type": "verdict",
            "verdict": {
                "state": classification.state,
                "summary": classification.summary,
                "confidence": classification.confidence,
                "category": classification.category,
            },
            "decision": decision.as_dict(),
        }
        if xp:
            event["xp_awarded"] = xp
        self._emit(event)
        return {"verdict": classification, "decision": decision}

    # -- negotiation entry point (the gate calls this) --

    def negotiate(
        self, user_message: str, history: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        from .coach import Coach

        outcome = Coach(self.provider).negotiate(
            user_message,
            self.policy.strictness,
            self._goals(),
            self.store,
            history=history,
        )
        self.policy.mark_concession(self.clock())
        self.policy.gate_open = False
        self._on_track_start = None  # a negotiation breaks the focus block
        event: dict[str, Any] = {
            "type": "negotiation",
            "concede": outcome.concede,
            "message": outcome.message,
        }
        if outcome.chore:
            event["chore"] = outcome.chore
        self._emit(event)
        return event

    # -- internals --

    def _goals(self) -> list[Goal]:
        rows = self.store.goals(include_done=False)
        return [
            Goal(
                goal_id=int(r["goal_id"]),
                title=str(r["title"]),
                minutes=int(r["minutes"]),
                difficulty=str(r["difficulty"]),
                done=bool(r["done"]),
            )
            for r in rows
        ]

    def _track_focus(self, classification: Classification, now: float) -> int:
        """Award XP when a sustained on_track span completes a goal block."""
        if classification.state == "on_track":
            if self._on_track_start is None:
                self._on_track_start = now
            return 0
        start = self._on_track_start
        self._on_track_start = None
        if start is None:
            return 0
        duration = now - start
        for goal in self._goals():
            if duration >= goal.minutes * 60:
                self.set_goal_done(goal.goal_id)
                return self.award_focus_session(goal.minutes, goal.difficulty)
        return 0

    def award_focus_session(self, goal_minutes: int, goal_difficulty: str) -> int:
        self._focus_streak += 1
        amount = award_for(goal_difficulty, self._focus_streak)
        self.store.xp_add(amount, f"focus block >= {goal_minutes}m ({goal_difficulty})")
        self._emit(
            {
                "type": "xp",
                "amount": amount,
                "total": self.store.xp_total(),
                "level": level_for(self.store.xp_total()),
            }
        )
        return amount

    def set_goal_done(self, goal_id: int) -> None:
        self.store.set_goal_done(goal_id, True)


class WatchThread(threading.Thread):
    """Optional background loop calling engine.tick() on a cadence."""

    def __init__(self, engine: Engine, interval_sec: float):
        super().__init__(daemon=True)
        self.engine = engine
        self.interval = interval_sec
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.engine.tick()
            except Exception:
                # a failed capture must never kill the loop, and the minutes
                # it would have bridged must never earn XP
                self.engine.note_capture_failure()

    def stop(self) -> None:
        self._stop.set()
