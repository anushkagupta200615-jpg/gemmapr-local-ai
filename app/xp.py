"""XP ledger: Solo-Levelling-flavoured progression for FOCUS MINUTES, not
for existing. Completing a focus block (>= goal.minutes of sustained
on_track) awards XP by goal difficulty, with a small streak bonus.
"""

from __future__ import annotations

XP_PER_DIFFICULTY = {"easy": 10, "medium": 25, "hard": 60}
LEVEL_PTS = [0, 50, 120, 250, 450, 700, 1000, 1500, 2100, 2800]


def award_for(goal_difficulty: str, streak: int = 0) -> int:
    base = XP_PER_DIFFICULTY.get(goal_difficulty, 10)
    bonus = min(streak, 5) * 2  # streak bonus capped at +10
    return base + bonus


def level_for(total_xp: int) -> int:
    lvl = 0
    for i, pts in enumerate(LEVEL_PTS):
        if total_xp >= pts:
            lvl = i + 1
    return max(lvl, 1)


def progress_in_level(total_xp: int) -> tuple[int, int]:
    """Return (xp_into_current_level, xp_needed_to_complete_level)."""
    idx = level_for(total_xp) - 1
    lower = LEVEL_PTS[idx]
    upper = LEVEL_PTS[idx + 1] if idx + 1 < len(LEVEL_PTS) else LEVEL_PTS[-1] + 900
    return total_xp - lower, upper - lower
