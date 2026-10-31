from app.xp import LEVEL_PTS, award_for, level_for, progress_in_level


def test_difficulty_weights():
    assert award_for("easy") == 10
    assert award_for("medium") == 25
    assert award_for("hard") == 60


def test_streak_bonus_capped():
    assert award_for("medium", streak=0) == 25
    assert award_for("medium", streak=3) == 25 + 6
    assert award_for("hard", streak=99) == 60 + 10  # cap at +10


def test_unknown_difficulty_falls_back_to_easy():
    assert award_for("impossible") == 10


def test_level_thresholds():
    assert level_for(0) == 1
    assert level_for(49) == 1
    assert level_for(50) == 2
    assert level_for(120) == 3
    assert level_for(100_000) == len(LEVEL_PTS)  # plateau at the top


def test_progress_in_level():
    into, needed = progress_in_level(0)
    assert (into, needed) == (0, 50)
    into, needed = progress_in_level(60)  # level 2 starts at 50
    assert into == 10
    assert needed == 70  # 50..120
