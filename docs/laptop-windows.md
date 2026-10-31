# Stage laptop runbook (Windows)

Windows is the *simpler* path: capture is native (`mss`), there is no
Wayland/X11 session dance, and Ollama runs as a background service.

## One-time setup (~10 min)

```powershell
# 1. model check — the exact tag must exist
ollama list          # want: gemma4:e2b

# 2. code
git clone https://github.com/anushkagupta200615-jpg/gemmapr-local-ai
cd gemmapr-local-ai
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 3. diagnostics — fix anything it flags before the demo
.\.venv\Scripts\python -m app selfcheck
```

Notes:

- **Ollama** for Windows installs a background service (system tray). No
  `ollama serve` needed; restart via the Start menu if it ever stops.
- Models can live on another drive: set the `OLLAMA_MODELS` environment
  variable (e.g. `D:\ollama_models`) **before** pulling.
- Console encoding is handled by the app itself (`_force_utf8_console()`
  reconfigures cp1252/cp936 consoles). `chcp 65001` is only needed if you
  want prettiest glyph rendering of arrows/emoji in the terminal.
- `selfcheck` prints: session type (`windows`), active window title reader
  (PowerShell path), ollama reachability, model-tag presence, mss/pillow
  import, strictness mode, sqlite writability. Exit code 0 = clean.

## Smoke run (no screen needed)

```powershell
.\.venv\Scripts\python -m app demo     # scripted 8-frame session; prints verdicts + XP
```

## Real run

```powershell
.\.venv\Scripts\python -m app run      # serves HUD on http://127.0.0.1:8765/
```

Open `http://127.0.0.1:8765/` in a browser (F11 for fullscreen) → set
goals → **▶ Start watching**. The gate overlay route is `/gate`.

Env knobs (all optional — same names on all platforms, see `docs/laptop.md`
table): `LETCHACK_MODEL`, `LETCHACK_OLLAMA_URL`, `LETCHACK_MOCK`,
`LETCHACK_STRICTNESS`, `LETCHACK_CAPTURE_INTERVAL`, `LETCHACK_WATCH`,
`LETCHACK_DATA_DIR`.

## The trap demo needs

1. a browser window (HUD, F11 fullscreen)
2. a distraction site ready to "accidentally" open (youtube/reddit tab parked)
3. `examples/gate_negotiation.md` from a morning
   `python examples/make_demo_artifacts.py` run, to show artifacts without
   waiting 30 real minutes for a completed block. On the stage laptop with
   the model available, prepend `LETCHACK_MOCK=0` (PowerShell:
   `$env:LETCHACK_MOCK="0"`) so the negotiation turn is voiced by the real
   gemma4:e2b.

## If something breaks live

- `ollama` down → tray icon missing? Start via Start menu; or `Get-Process ollama`.
- verdicts stuck `unknown` → `ollama ps` shows the model loaded?
- capture silent → `selfcheck` shows session type + whether a window
  title was read (PowerShell call); the Python process may need to run
  **not** as administrator to see window titles.
- everything else → `.\.venv\Scripts\python -m app demo` is the honest
  fallback demo.
