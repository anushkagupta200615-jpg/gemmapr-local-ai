import pytest

from app.classifier import MockProvider, OllamaProvider
from app.models import Frame, Goal

GOALS = [Goal(goal_id=1, title="Essay draft", minutes=30, difficulty="medium")]


def _frame(label: str) -> Frame:
    return Frame(image_b64="fakepng", label=label)


def _provider_resp(content: str) -> dict:
    return {"message": {"content": content}}


# ----- MockProvider: keyword verdicts -----


def _verdict(provider, **kw):
    return provider.classify_frames([_frame(kw["label"])], kw.get("goals", GOALS))[0]


def test_mockprovider_map():
    # Distraction keywords → drift
    for label in ("YouTube - Cats", "Reddit - front page", "Netflix - ShowX"):
        assert _verdict(MockProvider(), label=label).state == "drift"
    # Break keywords → break
    assert _verdict(MockProvider(), label="Spotify - This is Radiohead").state == "break"
    # Work keywords + goals → on_track
    assert _verdict(MockProvider(), label="VS Code - main.py").state == "on_track"
    assert _verdict(MockProvider(), label="Google Docs - Essay draft").state == "on_track"


# ----- OllamaProvider: strict JSON parsing -----


def test_ollamaprovider_parses_single_valid_json(monkeypatch):
    provider = OllamaProvider()
    rows = [
        {"state": "drift", "summary": "YouTube video", "confidence": 0.9,
         "category": "video"},
    ]
    monkeypatch.setattr(
        OllamaProvider, "_chat",
        lambda self, payload: _provider_resp(
            '{"verdicts": [%s]}' % ", ".join(
                __import__("json").dumps(r) for r in rows
            ))
    )
    out = provider.classify_frames([_frame("YouTube")], GOALS)
    assert out[0].state == "drift"
    assert out[0].category == "video"
    assert 0 <= out[0].confidence <= 1


def test_ollamaprovider_garbage_json_is_unknown(monkeypatch):
    provider = OllamaProvider()
    monkeypatch.setattr(
        OllamaProvider, "_chat",
        lambda self, payload: _provider_resp("this is not json")
    )
    out = provider.classify_frames([_frame("x")], GOALS)
    assert out[0].state == "unknown"


def test_ollamaprovider_model_error_is_unknown(monkeypatch):
    provider = OllamaProvider()
    def boom(self, payload): raise RuntimeError("server down")
    monkeypatch.setattr(OllamaProvider, "_chat", boom)
    out = provider.classify_frames([_frame("x")], GOALS)
    assert out[0].state == "unknown"


def test_ollamaprovider_bouncer_json(monkeypatch):
    provider = OllamaProvider()
    monkeypatch.setattr(
        OllamaProvider, "_chat",
        lambda self, payload: _provider_resp(
            '{"concede": false, "message": "The System holds."}'
        )
    )
    payload = provider.bouncer_turn("system prompt", [], "just 5 minutes")
    assert payload["concede"] is False
    assert "System" in payload["message"]


# ----- OllamaProvider: frames-never-leave-device guard -----


def test_ollamaprovider_rejects_non_loopback_url():
    # A remote model host would receive raw screenshots: refuse at construction
    for bad in ("http://10.0.0.5:11434", "https://api.example.com", "http://example.internal:8080"):
        with pytest.raises(ValueError, match="loopback"):
            OllamaProvider(base_url=bad)
    # loopback endpoints keep working
    OllamaProvider(base_url="http://127.0.0.1:11434")
    OllamaProvider(base_url="http://localhost:11434")


# ----- OllamaProvider: confidence must stay finite and in range -----


def test_parse_confidence_non_finite_is_zero(monkeypatch):
    provider = OllamaProvider()
    # json.loads("1e999") -> inf; a NaN via JSON "NaN" -> nan (non-finite)
    monkeypatch.setattr(
        OllamaProvider, "_chat",
        # flake8: noqa
        lambda self, payload: _provider_resp(
            '{"verdicts":[{"state":"drift","summary":"yt",'
            '"confidence":1e999,"category":"video"}]}'
        )
    )
    out = provider.classify_frames([_frame("YouTube")], GOALS)
    assert out[0].confidence == 0.0


def test_parse_confidence_out_of_range_is_zero(monkeypatch):
    provider = OllamaProvider()
    monkeypatch.setattr(
        OllamaProvider, "_chat",
        lambda self, payload: _provider_resp(
            '{"verdicts":[{"state":"drift","summary":"yt",'
            '"confidence":42.0,"category":"video"}]}'
        )
    )
    out = provider.classify_frames([_frame("YouTube")], GOALS)
    assert out[0].confidence == 0.0
