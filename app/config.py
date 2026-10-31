"""Central configuration for the app.

Everything is overridable via environment variables so the same code runs:
- on the demo laptop with the real local Gemma model (default)
- headless on the dev box / CI where the model is deliberately mocked

Rules honour the hackathon: cloud AI APIs are prohibited; the only real
model runtime is a local Ollama server on the same machine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings. Immutable; construct via Settings.from_env()."""

    # --- model ---
    model: str = "gemma4:e2b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    # CI and headless dev runs use the deterministic mock provider.
    mock_model: bool = False

    # --- capture ---
    screenshot_interval_sec: float = 10.0
    # identical consecutive frames are not re-classified (saves RAM/CPU on
    # 5 GB laptops): a hash is compared before spending model time.
    dedupe_frames: bool = True

    # --- accountability ---
    # user picks their strictness mode; changes gemma prompt + thresholds
    strictness: str = "medium"  # easy | medium | hard
    drift_streak_nudge_after: int = 2  # in "drift" classifications for hard/medium

    # --- server ---
    host: str = "127.0.0.1"
    port: int = 8765
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    watch_enabled: bool = False  # capture is OFF until the user opts in

    strictness_levels: tuple[str, ...] = ("easy", "medium", "hard")

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            model=os.environ.get("LETCHACK_MODEL", Settings.model),
            ollama_base_url=os.environ.get(
                "LETCHACK_OLLAMA_URL", Settings.ollama_base_url
            ),
            mock_model=_bool("LETCHACK_MOCK", False) or _bool("SKIP_MODEL_TESTS", False),
            screenshot_interval_sec=_float(
                "LETCHACK_CAPTURE_INTERVAL", Settings.screenshot_interval_sec
            ),
            dedupe_frames=_bool("LETCHACK_DEDUPE", Settings.dedupe_frames),
            strictness=os.environ.get("LETCHACK_STRICTNESS", Settings.strictness),
            host=os.environ.get("LETCHACK_HOST", Settings.host),
            port=int(os.environ.get("LETCHACK_PORT", Settings.port)),
            data_dir=Path(os.environ.get("LETCHACK_DATA_DIR", "./data")),
            watch_enabled=_bool("LETCHACK_WATCH", Settings.watch_enabled),
        )

    def normalised_strictness(self) -> str:
        s = (self.strictness or "medium").strip().lower()
        return s if s in self.strictness_levels else "medium"
