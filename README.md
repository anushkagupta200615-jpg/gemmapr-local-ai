# Letshack Bouncer

**An offline AI accountability assistant.** You tell it what you're supposed
to be doing. It watches your screen. When you drift, it doesn't guilt-trip you
into silence — it steps in like a bouncer, lets you *make your case*, remembers
every excuse you've made, and pays you XP only for focus you actually did.

Built for **Problem 08 (Gemma track)** — Hacktoberfest 2026. Everything runs
on **one local model: `gemma4:e2b` via Ollama**. No cloud. No second model.
No API keys. Works fully offline on a laptop.

```
┌────────────┐   frames    ┌─────────────┐  verdicts  ┌────────────┐
│  capture   │────────────▶│  gemma4:e2b │───────────▶│   policy   │
│ mss (X11/  │  dedupe +   │  batched    │  on_track/ │ hysteresis │
│ Windows)   │  downscale  │  vision call│  drift/…   │ 2 drifts → │
└────────────┘             └─────────────┘            │  GATE 🚪   │
                                                     └─────┬──────┘
        ┌──────────────────────┬─────────────────────────┴─────┐
        ▼                      ▼                               ▼
┌──────────────┐      ┌────────────────┐             ┌──────────────────┐
│ bouncer      │      │ evidence trail │             │ XP ledger        │
│ negotiation  │      │ SQLite, local, │             │ easy 10 / med 25 │
│ same model + │      │ one-tap delete │             │ hard 60 + streak │
│ case file    │      └────────────────┘             └──────────────────┘
└──────────────┘
```

## The core loop (and the honest design)

1. **You set goals** (title, minutes, difficulty: easy 10 XP / medium 25 / hard 60).
2. **You opt in** to watching — off by default, consent copy in the UI, all
   observations in one SQLite file with a **Delete my history** button.
3. Screenshots are captured on a cadence, hash-deduped, downscaled, and sent to
   the local Gemma. Verdicts: `on_track | drift | break | unknown`.
4. **Hysteresis, not twitchiness:** one drift frame does nothing. Two
   consecutive (medium; 1 on hard, 3 on easy) open **the gate**.
5. **The gate is negotiable.** Type your case. The reply comes from the *same*
   Gemma, fed a case file — what it actually saw, what you said last time.
   Lose a negotiation → penalty-zone chore. Win it honestly → ten-minute
   structured break, timer running.
6. **Only completed focus blocks pay XP** (goal-sized on_track spans, streak
   bonus capped at +10). Drifting to an XP screen does nothing. You level by
   focusing, not by existing.

## Run it (Linux laptop, X11; Windows works for capture too)

```bash
git clone https://github.com/anushkagupta200615-jpg/gemmapr-local-ai
cd gemmapr-local-ai && pip install -r requirements.txt
ollama pull gemma4:e2b          # one local model, ~few GB
python -m app selfcheck          # environment diagnostics — fix anything red
python -m app run                # HUD at http://127.0.0.1:8765/ · gate at /gate
```

Headless CI/self-education alternative: `python -m app demo` runs a scripted
8-frame session (mock provider) and prints the verdict stream + XP — no
display, no model required.

The optional Tauri shell (`src-tauri/`) wraps the same page: HUD window +
frameless always-on-top gate window. The browser alone is enough (F11).

## Where the model shows up (Gemma track compliance)

| surface | who does it |
|---|---|
| screen verdicts (`on_track/drift/break/unknown`) | gemma4:e2b, one batched vision call |
| nudge copy + negotiation voice | the same gemma4:e2b, case-file receipts in prompt |
| penalty-zone chore assignment | policy layer (deterministic consequence, not the model |
| XP math, levels, streaks | `app/xp.py` (deterministic ledger) |

CI and the dev box run with a deterministic **mock provider** (`SKIP_MODEL_TESTS=1`,
`LETCHACK_MOCK=1`) so tests never need a model — the demo laptop runs the real
`gemma4:e2b`. Artifacts in `examples/` label their provider honestly.

## Repo tour

- `app/` — engine core (`capture`, `classifier`, `policy`, `coach`, `xp`,
  `store`, `engine`) + HTTP/WS surface (`server.py`, `app/web/*` — no build tooling)
- `src-tauri/` — display shell (two windows; engine stays user-launched)
- `examples/` — real engine-run artifacts + the one-command generator
- `DEMO.md` — the 5-minute judge script · `docs/laptop.md` — stage runbook
- `tests/` — 56 pytest tests, fully headless
- `.github/workflows/ci.yml` — `pip install` + `pytest` per PR (all changes
  land through PRs, per hackathon rules)

## Privacy posture

Watching is opt-in. Verdicts store **categories + timestamps**, never raw
frames. The SQLite database lives under `data/` on your disk; one button (or
`Store.delete_all_history()`) wipes observations, decisions, XP, chores and
negotiations. No telemetry, no network beyond `127.0.0.1:11434` (Ollama).

## Team

Let'shack — Nihal Kumar (@nihalxkumar), Anushka Gupta (@anushkagupta200615-jpg).
MIT licensed. Issue tracker: `#2` engine core · `#6` engine surface ·
`#3/#4/#5` laptop capture/proof lanes.
