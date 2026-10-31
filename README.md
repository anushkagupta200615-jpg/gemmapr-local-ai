# Let'shack 🗡️

**An offline AI accountability & personal productivity assistant — powered by Gemma 4, running 100% locally.**

Hachtoberfest 2026 – Hack Day Sonipat · Newton School of Technology, Rishihood University · 31 Oct 2026

> Team **Let'shack** — Nihal Kumar (@nihalxkumar), Anushka Gupta (@anushkagupta200615-jpg)
> Problem 08 — *Build Anything with Gemma 4 – Local AI Innovation Challenge*

## Overview

You set your goals. The assistant holds you to them.

Let'shack is a locally running accountability partner: it watches your agreed goals, sends
adaptive nudges when you drift, negotiates with you when you push back, and turns progress
into a gamified journey — points, streaks, levels, and a digital avatar that grows as you do.

**No cloud. No Gemini. No fallback services.** Gemma runs on your laptop via Ollama,
which means the assistant works fully offline and your personal goals/behaviour never
leave your machine.

## Features

- 🎯 **Goal setting** — define your session goals; the assistant keeps them front-and-centre
- 👀 **Accountability loop** — adaptive nudges when attention drifts from the set goals
- 🤝 **Negotiation** — easy / medium / hard strictness modes for how firmly the assistant holds the line
- ⚔️ **Progress gamification** — Solo-Levelling-style points and streaks for completed focus
- 🪄 **Digital avatar** — visual feedback that reflects your consistent effort

## Installation

Requirements: Python 3.10+, [Ollama](https://ollama.com).

```bash
# 1. Install Ollama and pull the model (run once, then offline forever)
ollama pull gemma4:e2b

# 2. Clone and install the app
git clone https://github.com/anushkagupta200615-jpg/gemmapr-local-ai
cd gemmapr-local-ai
pip install -r requirements.txt
```

## Usage

```bash
ollama serve          # in a separate terminal, if Ollama isn't running as a service
python app/main.py
```

See [`examples/`](./examples) for real sample inputs and outputs.

## Models

| Model | Runtime | Why |
|---|---|---|
| `gemma4:e2b` | Ollama (local) | Fits memory-restricted laptops (~5 GB RAM); runs fully on-device |

## License

MIT — see [`LICENSE`](./LICENSE).
