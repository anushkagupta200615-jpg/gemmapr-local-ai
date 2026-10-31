from app.sample_data import default_goals


def test_sample_data_shape():
    goals = default_goals()
    assert len(goals) == 2
    for goal in goals:
        assert set(goal) == {"id", "title", "minutes", "difficulty"}


def test_sample_data_copies():
    a, b = default_goals(), default_goals()
    a[0]["title"] = "mutated"
    assert b[0]["title"] != "mutated"
