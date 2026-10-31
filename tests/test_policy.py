from app.models import Classification
from app.policy import Policy


def _v(state: str, summary: str = ""):
    return Classification(state=state, summary=summary, confidence=0.9)


def test_media_2_consecutive_drifts_open_gate_then_stop_spamming():
    p = Policy(strictness="medium")
    d1 = p.decide(_v("drift"), now=100)
    d2 = p.decide(_v("drift"), now=110)
    d3 = p.decide(_v("drift"), now=120)
    assert d1.action == "hold_silent"
    assert d2.action == "open_gate"
    assert d3.action == "hold_gate"  # no signal-spam once the gate is up


def test_easy_needs_three_strikes_hard_needs_one():
    easy = Policy(strictness="easy")
    assert easy.decide(_v("drift")).action == "hold_silent"
    assert easy.decide(_v("drift")).action == "hold_silent"
    assert easy.decide(_v("drift")).action == "open_gate"

    hard = Policy(strictness="hard")
    assert hard.decide(_v("drift")).action == "open_gate"


def test_on_track_closes_gate_and_resets():
    p = Policy(strictness="medium")
    p.decide(_v("drift")); p.decide(_v("drift"))  # gate open
    d = p.decide(_v("on_track"), now=200)
    assert d.action == "close_gate"
    # streak reset: single later drift does NOT reopen
    assert p.decide(_v("drift")).action == "hold_silent"


def test_break_resets_not_punishes():
    p = Policy(strictness="easy")  # 3 strikes to open; single drift stays silent
    p.decide(_v("drift"))
    assert p.decide(_v("break")).action == "hold_silent"
    assert p.decide(_v("drift")).action == "hold_silent"  # streak was reset


def test_break_closes_open_gate():
    p = Policy(strictness="hard")
    p.decide(_v("drift"))  # gate opens (hard = 1 strike)
    assert p.decide(_v("break")).action == "close_gate"


def test_unknown_does_not_trigger():
    p = Policy(strictness="hard")
    assert p.decide(_v("unknown")).action == "hold_silent"


def test_cooldown_after_concession_blocks_reopening():
    p = Policy(strictness="hard")
    p.decide(_v("drift"), now=0)
    p.mark_concession(now=100)  # gate closed + cooldown running
    assert p.decide(_v("drift"), now=150).action == "hold_silent"  # in cooldown
    assert p.decide(_v("drift"), now=100 + 601).action == "open_gate"
