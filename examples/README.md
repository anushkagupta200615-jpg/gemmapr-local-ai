# examples/ — real outputs

Every artifact here was **produced by running the actual engine pipeline**
(`Engine → Store → Policy → Coach → XP`), not hand-written. Regenerate them at
any time:

```bash
python examples/make_demo_artifacts.py          # deterministic run, mock voice
LETCHACK_MOCK=0 python examples/make_demo_artifacts.py   # on the stage laptop with ollama serving gemma4:e2b — Gemma's voice
```

| file | what it is | producer |
|---|---|---|
| `goals.json` | the session INPUT (3 goals with difficulty weights) | `store.add_goal()` |
| `session_timeline.json` | verdict-by-verdict stream: 2 drifts → gate opens → back on track → break | `engine.tick()` × 7 |
| `gate_negotiation.md` | an actual pair of negotiation turns; the model may hold or concede according to the medium-strictness policy | `engine.negotiate()` × 2 |
| `xp_log.json` | ledger after the completed focus block (easy 10 XP + streak bonus 2 = 12 XP) | `store.xp ledger` |
| `negotiation_events.json` | the WS bus events a HUD client would have received live | `engine._emit()` |

**Provider honesty:** artifacts regenerated in mock mode use deterministic
rules and each artifact says so in its `provider` field. On a stage laptop,
the hybrid run keeps verdicts deterministic on blank fixture frames and uses
Ollama for negotiation text. Model replies are not scripted: for example, an
apology alone does not meet the medium-strictness prompt's structured-reason
rule, so the model may hold the gate. The checked-in transcript records the
actual outcomes of its run.
