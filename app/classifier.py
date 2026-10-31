"""Verdict providers. ONE model rule: gemma4:e2b does all classification.

- MockProvider: deterministic keyword rules, zero model calls. Used on the
  dev box/CI (mock premise), never presented as the demo model.
- OllamaProvider: the real deal — batched frames in ONE vision call, strict
  JSON verdict parse, garbage-safe fallback to `unknown`.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit
from typing import Any

from .models import Classification, Frame, Goal

DISTRACTION_KEYS = (
    "youtube", "reddit", "instagram", "twitter", " x - ", "netflix", "tiktok",
    "facebook", "twitch", "steam", "discord",
)
BREAK_KEYS = ("spotify", "music", "break", "lunch")
WORK_KEYS = ("vscode", "code", "editor", "terminal", "docs", ".py", ".js", ".rs",
             "google docs", "word", "overleaf", "libreoffice")


class VerdictProvider:
    def classify_frames(
        self, frames: list[Frame], goals: list[Goal]
    ) -> list[Classification]:  # pragma: no cover
        raise NotImplementedError


class MockProvider(VerdictProvider):
    """Deterministic rules for tests/CI. The demo laptop never uses this."""

    name = "mock"

    def bouncer_turn(
        self, system: str, history: list[dict[str, str]], user_message: str
    ) -> dict[str, Any]:
        """Deterministic concession rules mirroring the persona contract.

        Word-token matching: "basically" must not unlock the "call" emergency
        route the way substring matching did.
        """
        import re

        msg = user_message.lower().strip()
        tokens = set(re.split(r"\W+", msg))
        if tokens & {"done", "finished", "completed", "submitted", "cleaned"}:
            concede, reply = True, "Verified. XP logged. Next goal loads on your command."
        elif tokens & {"emergency", "appointment", "call", "errand"}:
            concede, reply = True, "Approved — a real-world errand outranks the System. Return after."
        elif tokens & {"break", "coffee", "stretch", "rest", "nap"}:
            if self._persona_is_easy(system):
                concede, reply = True, "Ten minutes. The timer is on your feed. Go."
            elif self._persona_is_hard(system):
                concede, reply = False, "Breaks are earned. Finish the current block first."
            else:
                concede, reply = True, "Structured break granted: 10 minutes, timer running."
        elif "sorry" in tokens or "you're right" in msg or "fair" in tokens:
            concede, reply = True, "Apology accepted. Eyes on the goal — 25 minutes, then we talk."
        else:
            concede, reply = False, (
                "No. The receipts say otherwise — the first block is half an hour. Begin."
            )
        return {"concede": concede, "message": reply}

    @staticmethod
    def _persona_is_easy(system: str) -> bool:
        return "Current strictness: easy" in system

    @staticmethod
    def _persona_is_hard(system: str) -> bool:
        return "Current strictness: hard" in system

    def classify_frames(
        self, frames: list[Frame], goals: list[Goal]
    ) -> list[Classification]:
        out: list[Classification] = []
        for fr in frames:
            label = (fr.label or "").lower()
            if any(k in label for k in DISTRACTION_KEYS):
                st = "drift"
            elif any(k in label for k in BREAK_KEYS):
                st = "break"
            elif any(k in label for k in WORK_KEYS):
                st = "on_track" if goals else "unknown"
            else:
                st = "unknown"
            out.append(
                Classification(
                    state=st,
                    summary=label[:80] or "(no window title)",
                    confidence=0.9,
                    category={"drift": "video/social"}.get(st, "work" if st == "on_track" else "other"),
                )
            )
        return out


class OllamaProvider(VerdictProvider):
    """Batched single-call classification against the LOCAL ollama server."""

    name = "ollama"

    def __init__(self, model: str = "gemma4:e2b", base_url: str = "http://127.0.0.1:11434"):
        # Premise: raw frames never leave this device. A remote model host is
        # refused loudly at construction time — before a single capture runs.
        host = (urlsplit(base_url).hostname or "").lower()
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError(
                "LETCHACK_OLLAMA_URL must point at this machine (loopback "
                f"127.0.0.1/localhost/::1 only — screenshots must never leave "
                f"the device); got {base_url!r}"
            )
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        import ollama

        client = ollama.Client(host=self.base_url)
        return client.chat(model=self.model, **payload)

    def classify_frames(
        self, frames: list[Frame], goals: list[Goal], max_batch: int = 3
    ) -> list[Classification]:
        frames = frames[-max_batch:]
        goal_text = "; ".join(f"{g.title} ({g.difficulty}, {g.minutes}m)" for g in goals) or "no goals set yet"
        system = (
            "You are the attention System of an accountability app. Given recent "
            "screenshots of the user's screen, judge ATTENTION ONLY against the "
            "user's stated goals. Reply with STRICT JSON, no prose: "
            '{"verdicts":[{"state":"on_track|drift|break|unknown","summary":'
            '"<=12 words","confidence":0.0-1.0,"category":"work|video|social|'
            'communication|game|other"}]}. '
            f"The user's goals: {goal_text}"
        )
        images = [fr.image_b64 for fr in frames]
        try:
            resp = self._chat(
                {
                    "messages": [
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": "Classify these screen captures against the goals.",
                            "images": images,
                        },
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 200},
                }
            )
            return self._parse(resp, len(frames))
        except Exception:
            return [Classification(state="unknown", summary="model unavailable", confidence=0.0)] * len(frames)

    def bouncer_turn(
        self, system: str, history: list[dict[str, str]], user_message: str
    ) -> dict[str, Any]:
        """Negotiation turn: same local model, JSON {concede, message}."""
        import json as _json

        try:
            resp = self._chat(
                {
                    "messages": [
                        {"role": "system", "content": system},
                        *history,
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.6, "num_predict": 300},
                }
            )
            content = resp.get("message", {}).get("content", "") or "{}"
            payload = _json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("non-dict bouncer payload")
            payload.setdefault("concede", False)
            payload.setdefault("message", "")
            return payload
        except Exception:
            return {
                "concede": False,
                "message": "The System is stuttering. Try again — but the block still stands.",
            }

    def _parse(self, resp: dict[str, Any], count: int) -> list[Classification]:
        content = resp.get("message", {}).get("content", "") or "{}"
        raw: Any = {}
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            return [Classification(state="unknown", summary="unparseable verdict")] * count
        verdicts = raw.get("verdicts") if isinstance(raw, dict) else None
        if not isinstance(verdicts, list):
            return [Classification(state="unknown", summary="malformed verdict")] * count
        out: list[Classification] = []
        for i in range(count):
            item = verdicts[i] if i < len(verdicts) else {}
            state = str(item.get("state", "unknown")).lower()
            if state not in ("on_track", "drift", "break", "unknown"):
                state = "unknown"
            try:
                conf = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
            # non-finite (e.g. 1e999 -> inf) or out-of-range confidence must
            # not poison /api/state JSON encoding — that freezes the HUD
            if not 0.0 <= conf <= 1.0:
                conf = 0.0
            out.append(
                Classification(
                    state=state,
                    summary=str(item.get("summary", ""))[:80],
                    confidence=conf,
                    category=str(item.get("category", "other"))[:24],
                )
            )
        return out
