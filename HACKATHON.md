# Let'shack — Hacktoberfest 2026

**Event:** Hacktoberfest 2026 – Hack Day Sonipat
**Date:** 31 October 2026
**Venue:** Newton School of Technology, Rishihood University, Sonipat

## Team

- **Team name:** Let'shack
- **Members:**
  - Nihal Kumar — [@nihalxkumar](https://github.com/nihalxkumar)
  - Anushka Gupta — [@anushkagupta200615-jpg](https://github.com/anushkagupta200615-jpg)

## Problem Statement

**Special Track — Problem 08: Build Anything with Gemma 4 – Local AI Innovation Challenge**

We are building an **offline AI accountability & personal productivity assistant**.

The user sets personal goals in the app, and a locally running Gemma model acts as an
accountability partner — actively keeping the user on track with their set goals,
sending adaptive nudges when attention drifts, and helping them actually get work done.
An engaging visual layer (points, streaks, and a digital avatar) provides continuous
feedback on progress, in the spirit of gamified habit trackers.

Everything runs **100% locally on a laptop** — no cloud AI APIs, no Gemini, no fallback
services — addressing privacy and working reliably offline.

## AI Models Used and Justification

| Model | Runtime | Why this model |
|---|---|---|
| `gemma4:e2b` | Ollama (local) | Recommended variant for laptops with limited memory (~5 GB RAM on our dev machine). Runs entirely on-device, satisfies the "no cloud AI" mandate, and is fast enough for real-time, interactive nudges. |

## Workflow Note

Per the hackathon rules, this file is the only content of our initial commit. Every
subsequent change lands on `main` exclusively through pull requests that satisfy the
mandatory PR template and CI checks.
