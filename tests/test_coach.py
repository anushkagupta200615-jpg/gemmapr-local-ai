import pytest

from app.classifier import MockProvider
from app.coach import Coach, PENALTY_CHORES, persona_system_prompt
from app.models import Goal
from app.store import Store

GOALS = [Goal(goal_id=1, title="Essay", minutes=30, difficulty="medium")]


def test_case_file_includes_drifts_and_negotiations(tmp_path):
    s = Store(tmp_path / "t.db")
    s.add_verdict(1, 1000.0, "drift", summary="YouTube - Cats", category="video")
    s.add_negotiation("medium", "just five minutes", True, "ok, ten minutes")
    receipts = Coach.case_file(s)
    assert any("YouTube" in r for r in receipts)
    assert any("five minutes" in r for r in receipts)
    assert any("conceded" in r for r in receipts)


def test_receipts_appear_in_persona_prompt(tmp_path):
    s = Store(tmp_path / "t.db")
    s.add_verdict(1, 1000.0, "drift", summary="Reddit - memes", category="social")
    prompt = persona_system_prompt("hard", GOALS, Coach.case_file(s))
    assert "Reddit" in prompt
    assert "near-absolute" in prompt.lower()


def _make_store(tmp_path):
    return Store(tmp_path / "n.db")


def test_easy_concede_on_apology(tmp_path):
    s = _make_store(tmp_path)
    out = Coach(MockProvider()).negotiate("sorry, you're right", "easy", GOALS, s)
    assert out.concede is True
    assert out.chore == ""  # apology route never assigns chores


def test_medium_concedes_on_break(tmp_path):
    s = _make_store(tmp_path)
    out = Coach(MockProvider()).negotiate("quick coffee break?", "medium", GOALS, s)
    assert out.concede is True


def test_hard_holds_on_break_and_assigns_chore(tmp_path):
    s = _make_store(tmp_path)
    out = Coach(MockProvider()).negotiate("one quick break please", "hard", GOALS, s)
    assert out.concede is False
    assert out.chore in PENALTY_CHORES
    assert len(s.open_chores()) == 1


def test_hard_concedes_on_completion(tmp_path):
    s = _make_store(tmp_path)
    out = Coach(MockProvider()).negotiate("essay is finished and submitted", "hard", GOALS, s)
    assert out.concede is True


def test_negotiation_logged(tmp_path):
    s = _make_store(tmp_path)
    Coach(MockProvider()).negotiate("anything", "medium", GOALS, s)
    assert len(s.negotiations()) == 1
