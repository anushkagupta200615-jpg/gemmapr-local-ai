"""The bouncer persona: prompts + negotiation protocol.

Persona tone scales with strictness:
- easy: friendly coach, concedes on an honest acknowledgement
- medium: firm but fair; concedes for structured reasons (break/appointment/
  emergency/errand), otherwise holds
- hard: near-absolute; losing the negotiation earns a penalty-zone chore

Premise 3: the SAME gemma4:e2b voices this. The second opinion's "case file"
idea lives here: every negotiation carries receipts (recent contradicting
verdicts + logged excuses) so replies never feel generic.
"""

from __future__ import annotations

from typing import Any

from .models import Chore, Goal, NegotiationOutcome

PENALTY_CHORES = [
    "Wash the dishes in the sink",
    "20 minutes of desk/file cleanup",
    "Fold the laundry pile",
    "Take out the recycling",
]


def persona_system_prompt(strictness: str, goals: list[Goal], receipts: list[str]) -> str:
    tone = {
        "easy": "You are a warm, slightly cheeky coach. Concede when the user gives an honest acknowledgement.",
        "medium": (
            "You are firm but fair. Concede only for structured reasons "
            "(a scheduled break, an appointment/errand/emergency, urgent "
            "housekeeping). Otherwise hold the line and point at the goal."
        ),
        "hard": (
            "You are the System. Near-absolute. Concede only if the user states "
            "they completed the task, or a true emergency. Losing a negotiation "
            "means a penalty-zone chore."
        ),
    }[strictness]
    goal_text = (
        "; ".join(f"{g.title} ({g.difficulty}, {g.minutes}m)" for g in goals)
        or "no goals set yet"
    )
    receipts_text = "\n".join(f"- {r}" for r in receipts[-5:]) or "- (no receipts yet)"
    return (
        "You are the Accountability System that watches the user's screen. "
        f"Current strictness: {strictness}. {tone}\n"
        f"The user's goals: {goal_text}\n"
        "Receipts from the case file (what the System actually saw):\n"
        f"{receipts_text}\n\n"
        "Rules: max 3 sentences. Stay in character. Address exactly what the "
        "user said — you remember. End with a concrete next step OR a release.\n"
        "Reply with STRICT JSON only: "
        '{"concede": true|false, "message": "<=3 sentences"}'
    )


class Coach:
    """Runs negotiation turns through the provider (mock or real Ollama)."""

    def __init__(self, provider: Any):
        self.provider = provider

    @staticmethod
    def case_file(store) -> list[str]:
        """Receipts: what the System saw + what the user said about it."""
        lines: list[str] = []
        for d in store.drifts(5):
            lines.append(
                f"{d['ts']}: SAW '{d['summary']}'"
                f" (category {d['category'] or 'other'})"
            )
        for n in store.negotiations(5):
            lines.append(
                f"{n['ts']}: user said \"{n['user'][:60]}\" -> "
                f"{'conceded' if n['conceded'] else 'held the line'}"
            )
        return lines

    @staticmethod
    def _next_chore(store) -> str:
        idx = len(store.negotiations(50)) % len(PENALTY_CHORES)
        return PENALTY_CHORES[idx]

    def negotiate(
        self,
        user_message: str,
        strictness: str,
        goals: list[Goal],
        store,
        history: list[dict[str, str]] | None = None,
    ) -> NegotiationOutcome:
        system = persona_system_prompt(strictness, goals, self.case_file(store))
        payload = self.provider.bouncer_turn(system, history or [], user_message)
        concede = bool(payload.get("concede", False))
        message = str(payload.get("message", ""))[:600]
        chore = ""
        if not concede:
            chore = self._next_chore(store)
            store.assign_chore(chore, reason=f"lost a {strictness} negotiation")
        store.add_negotiation(
            mode=strictness, user=user_message, conceded=concede, reply=message,
            chore=chore,
        )
        return NegotiationOutcome(concede=concede, message=message, chore=chore)
