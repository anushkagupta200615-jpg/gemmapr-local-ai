from app.config import Settings


def test_defaults_minimal_adequate():
    s = Settings()
    assert s.model == "gemma4:e2b"
    assert s.watch_enabled is False  # opt-in watching (premise 4)
    assert s.normalised_strictness() == "medium"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LETCHACK_MODEL", "gemma4:e2b")
    monkeypatch.setenv("LETCHACK_MOCK", "1")
    monkeypatch.setenv("LETCHACK_STRICTNESS", "HARD")
    monkeypatch.setenv("LETCHACK_PORT", "7777")
    s = Settings.from_env()
    assert s.mock_model is True
    assert s.normalised_strictness() == "hard"
    assert s.port == 7777


def test_bad_strictness_coerces_to_medium(monkeypatch):
    monkeypatch.setenv("LETCHACK_STRICTNESS", "nuclear")
    assert Settings.from_env().normalised_strictness() == "medium"
