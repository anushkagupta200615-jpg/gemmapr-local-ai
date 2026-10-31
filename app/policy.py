"""Accountability policy: turns verdict sequences into decisions.

Hysteresis (from the second opinion, kept deliberately): one drift frame never
opens the gate; N consecutive drifts do. After a lost-and-conceded negotiation
a cooldown suppresses reopening so the app doesn't nag like a smoke detector.

Strictness thresholds: easy=3, medium=2, hard=1 consecutive drift verdicts.
"""

from __future__ import annotations

from .models import ACTIONS, Classification, Decision

_STRICTNESS_THRESHOLD = {"easy": 3, "medium": 2, "hard": 1}
DEFAULT_COOLDOWN_SEC = 600.0  # 10 minutes, per the design doc


class Policy:
    def __init__(
        self,
        strictness: str = "medium",
        cooldown_sec: float = DEFAULT_COOLDOWN_SEC,
    ):
        self.strictness = strictness
        self.drift_streak = 0
        self.gate_open = False
        self.last_gate_ts: float | None = None
        self.last_concession_ts: float | None = None
        self.cooldown_sec = cooldown_sec

    # -- helpers --

    def threshold(self) -> int:
        return _STRICTNESS_THRESHOLD.get(self.strictness, 2)

    def in_cooldown(self, now: float) -> bool:
        if self.last_concession_ts is None:
            return False
        return (now - self.last_concession_ts) < self.cooldown_sec

    def mark_concession(self, now: float) -> None:
        """Call after a negotiation ends (won or conceded): start cooldown,
        close the gate."""
        self.last_concession_ts = now
        self.gate_open = False
        self.drift_streak = 0

    # -- the decision --

    def decide(self, verdict: Classification, now: float = 0.0) -> Decision:
        if verdict.state not in ("on_track", "drift", "break", "unknown"):
            return Decision("hold_silent", "unclassifiable verdict")

        if verdict.state == "on_track":
            cleared = self.gate_open
            self.gate_open = False
            self.drift_streak = 0
            return Decision(
                "close_gate" if cleared else "hold_silent",
                "back on track" if cleared else "",
            )

        if verdict.state in ("break", "unknown"):
            # a legitimate break (or an honest unknown) is not drift; we don't
            # punish uncertainty — premise 4's transparency posture
            self.drift_streak = 0
            action = "close_gate" if self.gate_open else "hold_silent"
            self.gate_open = False
            return Decision(action, "break/unknown resets the watch" if action != "hold_silent" else "")

        # state == drift
        self.drift_streak += 1
        if self.gate_open:
            return Decision(
                "hold_gate",
                "still drifting while the gate is up",
                drift_streak=self.drift_streak,
            )
        if self.in_cooldown(now):
            return Decision(
                "hold_silent",
                "cooldown after a negotiation; watching quietly",
                drift_streak=self.drift_streak,
            )
        if self.drift_streak >= self.threshold():
            self.gate_open = True
            self.last_gate_ts = now
            return Decision(
                "open_gate",
                f"{self.drift_streak} consecutive drift verdicts (threshold "
                f"{self.threshold()} at strictness {self.strictness})",
                drift_streak=self.drift_streak,
            )
        return Decision(
            "hold_silent",
            f"drift detected (streak {self.drift_streak}/{self.threshold()})",
            drift_streak=self.drift_streak,
        )
