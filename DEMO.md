# DEMO — the 5-minute judge script (P08, Gemma track)

**Machine:** the demo laptop with Ollama serving `gemma4:e2b` — one-time setup in
`docs/laptop-windows.md` (Windows) or `docs/laptop.md` (Linux/X11).
**Audience:** judges sitting at your shoulder. **Vibe:** calm, then slightly evil.

## 0. Pre-flight (quiet room, before judges arrive)

```powershell
.\.venv\Scripts\python -m app selfcheck   # session=windows · model tag FOUND · mss yes
.\.venv\Scripts\python -m app run         # → Serving HUD on http://127.0.0.1:8765/
```

Linux/X11: same commands as `python -m app selfcheck` / `python -m app run`.
Exit code 0 from `selfcheck` = clean; fix anything it flags before opening the
browser.

Open `http://127.0.0.1:8765/` fullscreen (F11) **and** a second small window on
`http://127.0.0.1:8765/gate`, parked in a corner (that's the bouncer — it
always-on-top if you built the Tauri shell: `cargo tauri dev` inside
`src-tauri/`, see `docs/laptop.md`).

## 1. The setup (30 s)

- Show the HUD: avatar asleep, LEVEL 1, 0 XP.
- Add the goal live: *"Finish essay intro"* — medium, 30 min.
- Press **Start watching**. Read the consent line out loud: watching is opt-in,
  everything stays in a local SQLite file, one button wipes it.
- Switch to another window and deliberately open **YouTube** (or Reddit).

## 2. The trap (60–90 s)

- Normal screens are fine for a while — the bouncer does not twitch at a
  single drift frame. Stay on YouTube / a second tab until **2 consecutive
  drift verdicts** land (hysteresis: ~2 capture intervals ≈ 20 s at defaults).
- The HUD banner appears: **🚪 The bouncer is at your screen.** Point at the
  gate window (it never left the screen). Click *Face the gate →*.

## 3. The negotiation (the moment) (90 s)

In the gate chat, type:

> come on, just five more minutes of youtube, I'm basically studying

Strictness is medium → the System **holds the line** and quotes the case file
(receipts of what it actually saw). The penalty-zone chore is assigned.

Then request a structured break, for example:

> I need a quick coffee break, then I'll return to the essay

Medium strictness allows structured breaks. If the model grants it, the gate
releases; if it holds, keep working or make a more specific case. An apology
alone does not qualify for a concession at medium strictness.

## 4. The payoff (60 s)

- Stay on task one capture-interval. Show the **evidence trail** — verdicts
  with timestamps, all local.
- Show `examples/` artifacts from the morning run (`gate_negotiation.md`,
  `xp_log.json`) — same engine, same format, judge-readable.
- Complete a block → XP ring moves, level can tick. Mention streak bonus.

## 5. The close (30 s)

- **Delete my history** button → everything observables vanish. Goals stay.
- Kill watching. "It only exists while you ask it to."
- One line for judges: *one local Gemma model does everything — verdicts,
  nudge copy, and the negotiation voice. No cloud. No third API.*

## Failsafes

- `ollama` hiccup: verdicts degrade to `unknown` (never lie), engine keeps running.
- Capture broken: `selfcheck` prints exactly what's wrong — Linux: see
  `XDG_SESSION_TYPE` (Wayland is refused); Windows: browser over RDP, or display
  scaling not 100%.
- Browser issue: `python -m app demo` runs the whole pipeline headlessly and
  prints the verdict stream — still a demo.
