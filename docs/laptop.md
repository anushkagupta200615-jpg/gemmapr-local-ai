# Stage laptop runbook (Linux, X11)

## One-time setup (~10 min)

```bash
# 1. session check — MUST print x11 (Wayland is refused with instructions)
echo $XDG_SESSION_TYPE        # want: x11

# 2. model check — the exact tag must exist
ollama list                   # want: gemma4:e2b

# 3. code
git clone https://github.com/anushkagupta200615-jpg/gemmapr-local-ai
cd gemmapr-local-ai
pip install -r requirements.txt

# 4. diagnostics — fix anything it flags before the demo
python -m app selfcheck
```

`selfcheck` prints: session type, active window title reader status, ollama
reachability, model-tag presence, mss/pillow import, strictness mode, sqlite
writability. Exit code 0 = clean.

## Smoke run (no screen needed)

```bash
python -m app demo            # scripted 8-frame session; prints verdicts + XP
```

## Real run

```bash
python -m app run             # serves HUD on http://127.0.0.1:8765/
```

Open `http://127.0.0.1:8765/` → set goals → **Start watching**.

Env knobs (all optional):

| var | default | meaning |
|---|---|---|
| `LETCHACK_MODEL` | `gemma4:e2b` | exact ollama tag |
| `LETCHACK_OLLAMA_URL` | `http://127.0.0.1:11434` | ollama server |
| `LETCHACK_MOCK` | `0` | `1` = deterministic provider (no ollama needed) |
| `LETCHACK_STRICTNESS` | `medium` | `easy` 3 strikes / `medium` 2 / `hard` 1 |
| `LETCHACK_CAPTURE_INTERVAL` | `10` | seconds between captures |
| `LETCHACK_WATCH` | `0` | start watching immediately (else opt-in in UI) |
| `LETCHACK_DATA_DIR` | `./data` | sqlite location |

## Tauri shell (optional polish — the always-on-top gate)

The engine is the product; Tauri is a wrapper over `localhost:8765`.

```bash
# once
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
cargo install tauri-cli --version '^2'

# build+run (engine must already be running: python -m app run)
cd src-tauri && cargo tauri dev
```

Two windows appear: HUD + a frameless always-on-top gate window. If the build
is a problem at the venue: **skip it** — the browser window opened in F11
fullscreen IS the demo (identical page, identical behaviour). The gate overlay
route is `/gate`.

## The trap demo needs

1. a browser window (HUD, F11 fullscreen)
2. a distraction site ready to "accidentally" open (youtube/reddit tab parked)
3. `examples/gate_negotiation.md` from the morning `make_demo_artifacts.py`
   run, to show artifacts without waiting 30 real minutes for a completed block

## If something breaks live

- `ollama` down → `ollama serve` (and check `ps aux | grep ollama`)
- verdicts stuck `unknown` → `ollama ps` shows the model loaded?
- capture silent → `echo $XDG_SESSION_TYPE` must be `x11`
- everything else → `python -m app demo` is the honest fallback demo.
