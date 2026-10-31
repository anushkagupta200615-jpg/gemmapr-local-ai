"""Regenerate examples/ artifacts from a REAL engine run (deterministic).

This is not a replay of canned outputs: it boots the actual Engine, Store,
Policy, Coach and XP pipeline with a scripted frame source, runs a full
session — drift → gate → negotiation → focused block → break → XP — and
writes exactly what the engine recorded.

On the dev box the provider is the deterministic MockProvider (no model is
installed here, honestly labeled). On the stage laptop the same command with
gemma4:e2b running keeps the deterministic verdicts (FakeSource frames are
blank fixtures — nothing for a vision model to see) and lets the REAL model
voice the negotiation turn (issue #5):

    LETCHACK_MOCK=0 python examples/make_demo_artifacts.py   # real negotiation voice
    python examples/make_demo_artifacts.py                   # mock (CI-safe)

Every artifact carries a provider line stating exactly which voice produced
what — no part is presented as model-classified when it was not.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

os.environ.setdefault("LETCHACK_MOCK", "1")

from app.capture import FakeSource  # noqa: E402
from app.classifier import MockProvider, OllamaProvider, VerdictProvider  # noqa: E402
from app.config import Settings  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.store import Store  # noqa: E402
from app.xp import level_for  # noqa: E402


class MockVerdictsGemmaNegotiation(VerdictProvider):
    """Honest hybrid for the real-model artifact run.

    FakeSource frames are blank-fixture images that carry the scripted label —
    a real model has nothing to SEE there, so letting gemma4:e2b "judge" them
    would be theatre. Verdicts therefore stay deterministic (mock rules on the
    scripted labels); the REAL local gemma4:e2b voices the negotiation turn,
    which is legitimately text-only.
    """

    name = "mock-verdicts + gemma4:e2b-negotiation"

    def __init__(self, verdicts: MockProvider, negotiator: OllamaProvider):
        self._verdicts = verdicts
        self._negotiator = negotiator

    def classify_frames(self, frames, goals):
        return self._verdicts.classify_frames(frames, goals)

    def bouncer_turn(self, system, history, user_message):
        return self._negotiator.bouncer_turn(system, history, user_message)


def main() -> int:
    out_dir = Path(__file__).resolve().parent
    tmp = tempfile.mkdtemp(prefix="letshack-examples-")

    settings = Settings.from_env()  # honours LETCHACK_MOCK=0 for real-model runs
    if settings.mock_model:
        provider = MockProvider()
        provider_name = "mock (deterministic rules; no model on this machine)"
    else:
        provider = MockVerdictsGemmaNegotiation(
            verdicts=MockProvider(),
            negotiator=OllamaProvider(
                model=settings.model, base_url=settings.ollama_base_url
            ),
        )
        provider_name = (
            "hybrid: verdicts = mock rules on scripted-labelled BLANK-FIXTURE "
            f"frames (never real screens) · negotiation voice = ollama:{settings.model}"
        )

    store = Store(os.path.join(tmp, "session.db"))
    engine = Engine(
        settings=settings,
        store=store,
        provider=provider,
    )

    store.add_goal("Warm-up sprint: outline notes", minutes=0, difficulty="easy")
    store.add_goal("Finish essay introduction", minutes=30, difficulty="medium")
    store.add_goal("Clean up project notes", minutes=15, difficulty="easy")

    engine.enable_watch(
        FakeSource(
            [
                "VS Code - essay_draft.py",
                "Google Docs - Essay introduction",
                "YouTube - focus lofi beats mix 10 hours",     # drift #1
                "Reddit - r/GetStudying - top posts today",    # drift #2 -> gate
                "Google Docs - Essay introduction",            # back to work
                "Google Docs - Essay introduction",
                "Spotify - Coffee break mix",                  # break: block ends
            ]
        )
    )

    events: list[dict] = []
    engine.subscribe(events.append)

    t = 1000.0
    timeline = []
    for step in range(7):
        result = engine.tick(now=t)
        if "verdict" in result:
            v = result["verdict"]
            timeline.append(
                {
                    "t": t,
                    "state": v.state,
                    "summary": v.summary,
                    "category": v.category,
                    "confidence": v.confidence,
                    "decision": result["decision"].as_dict(),
                }
            )
        t += 60.0

    # the gate moment: student tries to talk their way out
    nego_1 = engine.negotiate(
        "come on, just five more minutes of youtube, i'm basically studying",
        history=[],
    )
    nego_2 = engine.negotiate("ok ok, you're right. back to the essay now.", history=[])

    # ---- goals.json (the INPUT) ----
    (out_dir / "goals.json").write_text(
        json.dumps(
            {
                "provider": provider_name,
                "goals": [
                    {"title": "Warm-up sprint: outline notes", "minutes": 0,
                     "difficulty": "easy"},
                    {"title": "Finish essay introduction", "minutes": 30,
                     "difficulty": "medium"},
                    {"title": "Clean up project notes", "minutes": 15,
                     "difficulty": "easy"},
                ],
            },
            indent=2,
        )
        + "\n"
    )

    # ---- session_timeline.json (verdicts + decisions stream) ----
    (out_dir / "session_timeline.json").write_text(
        json.dumps(
            {
                "provider": provider_name,
                "strictness": "medium",
                "policy": "2 consecutive drift verdicts -> gate; 10min cooldown after negotiation",
                "frames": timeline,
            },
            indent=2,
        )
        + "\n"
    )

    # ---- gate_negotiation.md (the trap moment transcript) ----
    lines = [
        "# Gate negotiation transcript",
        "",
        f"Provider: **{provider_name}**",
        "",
        f"Pipeline: screenshots → verdicts ({provider_name}) → policy (2-drift gate)",
        "→ bouncer persona (same model) → case-file receipts fed into every reply.",
        "",
        "## The System is holding your screen",
        "",
        "**Student:** come on, just five more minutes of youtube, i'm basically studying",
        "",
        f"**System:** {nego_1['message']}",
        "",
        f"*(conceded: {str(nego_1['concede']).lower()})*",
        "",
        "**Student:** ok ok, you're right. back to the essay now.",
        "",
        f"**System:** {nego_2['message']}",
        "",
        f"*(conceded: {str(nego_2['concede']).lower()})*",
        "",
        "## Case-file receipts the System used (store.drifts/negotiations)",
        "",
    ]
    for r in store.drifts(5):
        lines.append(f"- SAW {r['summary']!r} ({r['category'] or 'other'})")
    for n in store.negotiations(5):
        lines.append(
            f"- you said {n['user']!r} -> "
            f"{'conceded' if n['conceded'] else 'held the line'}"
        )
    (out_dir / "gate_negotiation.md").write_text("\n".join(lines) + "\n")

    # ---- xp_log.json (the ledger after a completed focus block) ----
    ledger = [
        dict(r)
        for r in store.conn.execute("SELECT * FROM xp ORDER BY xp_id")
    ]
    total = store.xp_total()
    (out_dir / "xp_log.json").write_text(
        json.dumps(
            {
                "provider": provider_name,
                "allocator": "focus block completion: medium=25, easy=10, hard=60 + streak bonus (cap +10)",
                "ledger": ledger,
                "total_xp": total,
                "level": level_for(total),
            },
            indent=2,
        )
        + "\n"
    )

    # ---- negotiation_events.json (engine event bus dump) ----
    (out_dir / "negotiation_events.json").write_text(
        json.dumps(
            {
                "provider": provider_name,
                "note": "what the WS bus pushed to the HUD during the run",
                "negotiations": [
                    {"concede": nego_1["concede"], "message": nego_1["message"],
                     "chore": nego_1.get("chore", "")},
                    {"concede": nego_2["concede"], "message": nego_2["message"],
                     "chore": nego_2.get("chore", "")},
                ],
                "verdict_events": events,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"examples/ regenerated from a real engine run ({provider_name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
