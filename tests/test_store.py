import time

from app.store import Store
from app.xp import award_for


def test_goals_roundtrip(tmp_path):
    s = Store(tmp_path / "t.db")
    gid = s.add_goal("Write essay", minutes=30, difficulty="hard")
    rows = s.goals()
    assert rows[0]["title"] == "Write essay"
    assert rows[0]["difficulty"] == "hard"
    s.set_goal_done(gid)
    assert s.goals(include_done=False) == []


def test_verdicts_and_drifts(tmp_path):
    s = Store(tmp_path / "t.db")
    s.add_verdict(1, time.time(), "drift", summary="YouTube", category="video")
    s.add_verdict(2, time.time(), "on_track", summary="VS Code")
    assert len(s.verdicts()) == 2
    drifts = s.drifts()
    assert len(drifts) == 1 and drifts[0]["state" if "state" in drifts[0] else "summary"]


def test_xp_total_and_focus_flow(tmp_path):
    s = Store(tmp_path / "t.db")
    s.xp_add(award_for("medium", 0))
    s.xp_add(award_for("easy", 3))
    assert s.xp_total() == 25 + 16


def test_negotiation_and_chore_logs(tmp_path):
    s = Store(tmp_path / "t.db")
    s.add_negotiation("hard", "just 5 more minutes", False, "No.", "Wash dishes")
    s.assign_chore("Wash dishes")
    assert len(s.negotiations()) == 1
    assert s.negotiations()[0]["conceded"] == 0
    assert len(s.open_chores()) == 1


def test_delete_all_history_keeps_goals(tmp_path):
    s = Store(tmp_path / "t.db")
    gid = s.add_goal("Keep me", minutes=5, difficulty="easy")
    s.add_verdict(1, time.time(), "drift", summary="x")
    s.xp_add(10)
    s.assign_chore("Cleanup")
    s.add_negotiation("medium", "please", True, "go on")
    s.delete_all_history()
    assert s.verdicts() == []
    assert s.xp_total() == 0
    assert s.open_chores() == []
    assert s.negotiations() == []
    assert s.goals()[0]["goal_id"] == gid
