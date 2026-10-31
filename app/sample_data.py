"""Sample data shared by the smoke tests and CI."""

GOALS_SAMPLE = [
    {"id": 1, "title": "Write essay introduction", "minutes": 30, "difficulty": "easy"},
    {"id": 2, "title": "Refactor parser module", "minutes": 90, "difficulty": "hard"},
]


def default_goals() -> list[dict]:
    """Return the starter goal set used for first runs and demos."""
    return [g.copy() for g in GOALS_SAMPLE]
