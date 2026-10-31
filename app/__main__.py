"""CLI entry points.

    python -m app selfcheck   environment diagnostics for the stage laptop
    python -m app run         serve the real engine (HUD + gate) on :8765
    python -m app demo        tiny headless smoke run (FakeSource + MockProvider)
Anything else prints usage.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .capture import active_window_title, session_type


def _ollama_status(base_url: str) -> tuple[bool, list[str]]:
    """(reachable, model tags). No third-party import needed."""
    import json as _json
    import urllib.request

    try:
        host = base_url.split("//", 1)[-1]
        port = host.rsplit(":", 1)[-1] if ":" in host else "11434"
        with socket.create_connection(("127.0.0.1", int(port)), timeout=1.5):
            pass
    except OSError:
        return False, []
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=3) as r:
            data = _json.loads(r.read().decode())
        return True, [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return True, []  # server reachable but tags endpoint failed


def selfcheck() -> int:
    code = 0
    print(f"session type : {session_type()}")
    print(f"window title : {active_window_title()!r}")
    ok, models = _ollama_status("http://127.0.0.1:11434")
    print(f"ollama server: {'reachable' if ok else 'NOT reachable (start `ollama serve`)'}")
    if ok:
        wanted = os.environ.get("LETCHACK_MODEL", "gemma4:e2b")
        have = [m for m in models if m.startswith(wanted)] or (
            [m for m in models if wanted.split(":")[0] in m]
        )
        print(f"model tag    : {wanted} -> {'FOUND ' + have[0] if have else 'MISSING (ollama pull ' + wanted + ')'}")
        if not have:
            code = 1
    else:
        code = 1
    print(f"mss installed: ", end="")
    try:
        import mss  # noqa: F401
        from PIL import Image  # noqa: F401

        print("yes")
    except ImportError:
        print("no (pip install -r requirements.txt)")
        code = 1
    from .config import Settings

    s = Settings.from_env()
    print(f"strictness   : {s.normalised_strictness()} (threshold by policy)")
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "diag.db")
        print(f"sqlite       : writable (probed at {db})")
    return code


def demo() -> int:
    """Headless smoke run of the engine with scripted frames."""
    import os

    tmp = tempfile.mkdtemp(prefix="letshack-demo-")
    os.environ["LETCHACK_DATA_DIR"] = tmp

    from .capture import FakeSource
    from .classifier import MockProvider
    from .config import Settings
    from .engine import Engine
    from .store import Store

    s = Settings.from_env()
    store = Store(str(os.path.join(tmp, "demo.db")))
    engine = Engine(settings=s, store=store, provider=MockProvider())
    source = FakeSource(
        [
            "YouTube - Funny cats compilation",
            "Reddit - r/funny - Top posts",
            "YouTube - Cats again",
            "Visual Studio Code - essay_draft.py",
            "Google Docs - Essay introduction",
            "Google Docs - Essay introduction",
            "Google Docs - Essay introduction",
            "Spotify - Chill mix",  # finish the block: transition triggers XP
        ]
    )
    store.add_goal("Write essay introduction (smoke goal)", minutes=0, difficulty="medium")
    print("watch: scripted 8-frame session (drift → gate → focused block → break/XP)")
    engine.enable_watch(source)
    for offset in range(0, 80, 10):
        engine.tick(now=1000.0 + offset)
    print(f"final xp total: {store.xp_total()}")
    for row in store.verdicts(limit=7):
        print(f"  verdict: {row['state']:<10} {row['summary']}")
    return 0


def run() -> int:
    """Serve the real engine (Ollama provider unless LETCHACK_MOCK=1)."""
    from .classifier import MockProvider, OllamaProvider
    from .config import Settings
    from .engine import Engine
    from .store import Store

    s = Settings.from_env()
    store = Store(str(s.data_dir / "letshack.db"))
    provider = MockProvider() if s.mock_model else OllamaProvider(
        model=s.model, base_url=s.ollama_base_url
    )
    engine = Engine(settings=s, store=store, provider=provider)
    if s.watch_enabled:
        from .capture import get_source

        engine.enable_watch(get_source())

    from .server import serve

    print(f"Serving HUD on http://{s.host}:{s.port}/ (gate: /gate)")
    print(f"model={provider.name}:{getattr(provider, 'model', 'mock')} "
          f"strictness={s.normalised_strictness()} db={store.path}")
    serve(engine)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "selfcheck":
        return selfcheck()
    if argv and argv[0] == "run":
        return run()
    if argv and argv[0] == "demo":
        return demo()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
