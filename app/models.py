"""Domain models shared by all layers.

Plain, JSON-friendly dataclasses so the API layer can return them directly
and tests (and the mock provider) can build them trivially.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

STATES = ("on_track", "drift", "break", "unknown")
ACTIONS = ("hold_silent", "open_gate", "hold_gate", "close_gate", "reward_xp")
DIFFICULTIES = ("easy", "medium", "hard")


@dataclass(frozen=True)
class Classification:
    """Gemma's verdict on one observation of the user's screen."""

    state: str  # on_track | drift | break | unknown
    summary: str
    confidence: float = 0.0
    category: str = ""  # e.g. research, coding, social, video

    def is_valid(self) -> bool:
        return self.state in STATES


@dataclass(frozen=True)
class Frame:
    """One captured observation. Carries a short hash for dedupe so identical
    consecutive screens never waste model time."""

    image_b64: str  # base64 JPEG
    ts: float = field(default_factory=time.time)
    label: str = ""  # active window title / process, when available
    width: int = 0
    height: int = 0

    @property
    def hash(self) -> str:
        return hashlib.sha1(self.image_b64.encode()).hexdigest()


@dataclass(frozen=True)
class Goal:
    goal_id: int
    title: str
    minutes: int = 30
    difficulty: str = "easy"
    done: bool = False


@dataclass(frozen=True)
class Decision:
    """What the accountability engine does after a classification."""

    action: str  # one of ACTIONS
    message: str = ""
    xp_awarded: int = 0
    drift_streak: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "message": self.message,
            "xp_awarded": self.xp_awarded,
            "drift_streak": self.drift_streak,
        }


@dataclass(frozen=True)
class NegotiationOutcome:
    """Result of one bouncer turn."""

    concede: bool
    message: str
    chore: str = ""  # filled when the negotiation is lost and a penalty-zone
    # chore is assigned


@dataclass(frozen=True)
class Chore:
    """Penalty-zone: a verified boring chore the user must finish before the
    session can count again (a Solo-Levelling-flavoured consequence)."""

    title: str
    reason: str
    assigned_at: float = field(default_factory=time.time)
    done: bool = False
