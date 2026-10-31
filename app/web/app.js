/* Let'shack bouncer front-end. Vanilla JS, no build step, no CDN.
   One file serves both pages (HUD + gate) keyed on <body data-page>. */
"use strict";

const $ = (id) => document.getElementById(id);
const page = document.body.dataset.page;

async function api(path, body) {
  const res = await fetch(path, body ? {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  } : {});
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

const STATE_LABELS = {
  on_track: ["model: on track", "s-ok"],
  drift: ["model: drift", "s-drift"],
  break: ["model: break", "s-break"],
  unknown: ["model: unclear", "s-unknown"],
};

const PIP_ART = `<svg viewBox="0 0 128 128" role="img" aria-label="Pip, the ticket punch mascot">
  <ellipse cx="64" cy="111" rx="36" ry="6" fill="#17281e" opacity=".3"/>
  <path d="M25 82h78v19q0 6-7 6H32q-7 0-7-6z" fill="#375c4d" stroke="#d7e2ca" stroke-width="3"/>
  <path d="M37 83V67q0-8 9-8h36l16 12v12z" fill="#e0a653" stroke="#f5d49b" stroke-width="3" stroke-linejoin="round"/>
  <path d="M45 59 71 25q4-5 10-1l17 13q5 4 1 9L80 66" fill="#c9813e" stroke="#f5d49b" stroke-width="3" stroke-linejoin="round"/>
  <path d="m62 41 18-22q4-5 9-1l8 6q4 3 1 7L79 53" fill="#e0a653" stroke="#f5d49b" stroke-width="3" stroke-linejoin="round"/>
  <circle cx="48" cy="68" r="5" fill="#d4774b" stroke="#253d2f" stroke-width="2"/>
  <ellipse class="pip-eye" cx="56" cy="73" rx="3.2" ry="4.2"/><ellipse class="pip-eye" cx="73" cy="73" rx="3.2" ry="4.2"/>
  <circle class="pip-pupil" cx="57" cy="72" r="1.1"/><circle class="pip-pupil" cx="74" cy="72" r="1.1"/>
  <path class="pip-brow pip-brow-left" d="M51 66h10"/><path class="pip-brow pip-brow-right" d="M68 66h10"/>
  <path class="pip-mouth" d="M57 82q7 5 14 0"/>
  <circle class="pip-cheek" cx="48" cy="79" r="3"/><circle class="pip-cheek" cx="80" cy="79" r="3"/>
  <path d="M39 97h48" stroke="#d4774b" stroke-width="3" stroke-linecap="round"/>
  <circle cx="64" cy="97" r="3" fill="#f8e8c6"/>
</svg>`;

function setPipFace(state) {
  const visual = $("mascot-visual");
  if (!visual) return;
  if (!visual.firstElementChild) visual.innerHTML = PIP_ART;
  visual.firstElementChild.dataset.face = state || "unknown";
}

function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* ---------------- HUD ---------------- */

function renderAvatar(state, watchOn, hasVerdict) {
  const [label, cls] = !watchOn
    ? ["watch off", "s-unknown"]
    : hasVerdict
      ? (STATE_LABELS[state] || STATE_LABELS.unknown)
      : ["waiting for check", "s-unknown"];
  setPipFace(watchOn ? state : "unknown");
  const ring = $("xp-ring");
  if (ring) {
    ring.classList.remove("drift", "break");
    if (cls === "s-drift") ring.classList.add("drift");
    if (cls === "s-break") ring.classList.add("break");
  }
  if ($("avatar-state")) {
    $("avatar-state").textContent = label;
    $("avatar-state").className = "avatar-state " + cls;
  }
}

function pipNudge(state, watchOn, gateOpen, goals) {
  const goal = (goals || []).find((g) => !g.done);
  const target = goal ? `“${goal.title}”` : "your mission";
  if (gateOpen) return "The latest checks reached the drift threshold. Review the reports and tell me what changed.";
  if (!watchOn) return "I’m Pip, your ticket punch. Add a mission; nothing gets classified until you turn screen checks on.";
  if (state === "break") return "The latest check was marked as a break. Take the time you need; I won’t count it as drift.";
  if (!goal) return "Screen checks are on, but there’s no active mission to compare them with. Add one when you’re ready.";
  if (state === "on_track") return `The latest check was marked on track for ${target}. Keep going if that still feels right.`;
  if (state === "drift") return `The latest check was marked as drift against ${target}. It may be a false read; want to return to the task?`;
  return `Screen checks are on. There isn’t a clear classification yet for ${target}.`;
}

function renderState(s) {
  if ($("strictness")) $("strictness").textContent = s.strictness;
  if ($("level")) $("level").textContent = String(s.level).padStart(2, "0");
  if ($("xp-total")) $("xp-total").textContent = String(s.xp_total);
  if ($("focus-streak")) {
    $("focus-streak").textContent =
      s.focus_streak > 0 ? `${s.focus_streak} completed blocks` : "No completed blocks yet";
  }
  const ring = $("xp-ring");
  if (ring) {
    const pct = s.xp_level_size > 0 ? s.xp_into_level / s.xp_level_size : 0;
    ring.style.strokeDashoffset = String(119 - 119 * Math.max(0, Math.min(1, pct)));
  }
  // avatar mirrors the most recent verdict while watching
  const last = s.recent_verdicts && s.recent_verdicts[0];
  renderAvatar(last ? last.state : "unknown", s.watch_on, Boolean(last));
  if ($("mascot-line")) {
    const line = pipNudge(last ? last.state : "unknown", s.watch_on, s.gate_open, s.goals);
    if ($("mascot-line").textContent !== line) $("mascot-line").textContent = line;
  }
  const checkText = s.watch_on ? "Screen checks are on" : "Screen checks are off";
  if ($("header-watch")) $("header-watch").textContent = s.watch_on ? "Checks on" : "Watching off";
  [$("status-dot"), $("check-dot")].filter(Boolean).forEach((dot) => dot.classList.toggle("is-on", s.watch_on));
  if ($("watch-label")) $("watch-label").textContent = checkText;
  if ($("watch-detail")) $("watch-detail").textContent = s.watch_on
    ? (last ? "Screen checks are enabled. The latest result is shown below." : "Screen checks are enabled. Waiting for the first classification.")
    : "Nothing is being captured. Turn checks on when you’re ready.";
  if ($("capture-cadence")) $("capture-cadence").textContent = `${s.capture_interval_sec || 10} seconds`;
  if ($("model-name")) $("model-name").textContent = s.model_name || "Ollama model";
  if ($("processing-note")) $("processing-note").textContent = s.model_name === "mock provider"
    ? "Mock mode is active. Captured frames are classified by the mock provider instead of being sent to Ollama. Raw images aren’t saved; metadata and history are stored in the local database."
    : "When enabled, screen frames go to your configured Ollama model for classification. Raw images aren’t saved; verdicts and related history are stored in the local database.";
  if ($("last-check")) $("last-check").textContent = last ? fmtTime(last.ts) : "No checks yet";

  // goals
  const gl = $("goals");
  if (gl) {
    gl.innerHTML = "";
    (s.goals || []).forEach((g) => {
      const li = document.createElement("li");
      // model/user-derived text is rendered as TEXT, never markup: goal
      // titles could otherwise run script inside the local app
      const title = document.createElement("span");
      if (g.done) title.className = "done";
      title.textContent = g.title;
      const meta = document.createElement("span");
      meta.className = "t";
      meta.textContent = `${g.difficulty} · ${g.minutes}m`;
      li.append(title, meta);
      gl.appendChild(li);
    });
    if (!(s.goals || []).length) gl.innerHTML = "<li><i>No missions yet</i></li>";
  }
  const missionFeature = $("mission-feature");
  if (missionFeature) {
    const active = (s.goals || []).find((g) => !g.done);
    missionFeature.innerHTML = "";
    const label = document.createElement("span");
    label.className = "quiet-label";
    label.textContent = active ? "NEXT UP" : "WORKSPACE";
    const title = document.createElement("strong");
    title.textContent = active ? active.title : "No active mission yet";
    const detail = document.createElement("p");
    detail.textContent = active ? `${active.minutes} minute focus block · ${active.difficulty} effort` : "Add one clear task and a focus block length.";
    missionFeature.append(label, title, detail);
  }

  // evidence trail
  const tl = $("verdicts");
  if (tl) {
    tl.innerHTML = "";
    (s.recent_verdicts || []).forEach((v) => {
      const li = document.createElement("li");
      // v.summary is model-written — render as text only
      const st = document.createElement("span");
      st.className = "s-" + v.state;
      st.textContent = v.state;
      const sum = document.createElement("span");
      sum.textContent = v.summary || "—";
      const t = document.createElement("span");
      t.className = "t";
      t.textContent = fmtTime(v.ts);
      li.append(st, sum, t);
      tl.appendChild(li);
    });
    if (!(s.recent_verdicts || []).length) tl.innerHTML = "<li><i>no observations yet</i></li>";
  }

  // penalty zone
  const cl = $("chores");
  if (cl) {
    cl.innerHTML = "";
    (s.open_chores || []).forEach((c) => {
      const li = document.createElement("li");
      const title = document.createElement("span");
      title.textContent = c.title;
      const reason = document.createElement("span");
      reason.className = "t";
      reason.textContent = c.reason || "penalty";
      li.append(title, reason);
      cl.appendChild(li);
    });
    if ($("chores-empty")) {
      $("chores-empty").style.display = (s.open_chores || []).length ? "none" : "block";
    }
  }

  const btn = $("watch-toggle");
  if (btn) {
    btn.innerHTML = s.watch_on ? "Pause screen checks" : "Start screen checks";
    btn.dataset.watchOn = s.watch_on ? "true" : "false";
  }
  if ($("gate-banner")) {
    $("gate-banner").classList.toggle("hidden", !s.gate_open);
    if (s.gate_open && $("gate-banner-detail")) {
      $("gate-banner-detail").textContent = `${s.drift_streak} consecutive drift checks met the ${s.strictness} threshold (${s.drift_threshold}). Review the reports before responding.`;
    }
  }
}

async function hudLoop() {
  try {
    renderState(await api("/api/state"));
  } catch (e) { /* server hiccup; next poll retries */ }
}

function hudEvents() {
  const ws = new WebSocket(
    (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { if ($("conn")) $("conn").textContent = "live feed: connected"; };
  ws.onclose = () => {
    if ($("conn")) $("conn").textContent = "live feed: reconnecting…";
    setTimeout(connectWS, 2000);
  };
  ws.onmessage = (ev) => {
    try {
      const e = JSON.parse(ev.data);
      if (e.type === "verdict") hudLoop();
      if (e.type === "xp") hudLoop();
      if (e.type === "negotiation") hudLoop();
      if (e.type === "watch") hudLoop();
    } catch (_) {}
  };
  return ws;
}
let connectWS = hudEvents;

async function hudInit() {
  const form = $("goal-form");
  if (form) form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    await api("/api/goals", {
      title: $("goal-title").value,
      minutes: parseInt($("goal-minutes").value || "30", 10),
      difficulty: $("goal-difficulty").value,
    });
    $("goal-title").value = "";
    hudLoop();
  });
  const wt = $("watch-toggle");
  if (wt) wt.addEventListener("click", async () => {
    $("watch-error").textContent = "";
    try {
      const on = wt.dataset.watchOn === "true";
      await api("/api/watch", { on: !on });
      hudLoop();
    } catch (e) { $("watch-error").textContent = e.message; }
  });
  const wipe = $("wipe");
  if (wipe) wipe.addEventListener("click", async () => {
    if (!confirm("Delete every observation, verdict, decision, XP and chore record? Goals are kept.")) return;
    await api("/api/history/delete");
    hudLoop();
  });
  connectWS();
  await hudLoop();
  setInterval(hudLoop, 3000); // heartbeat in addition to WS pushes
}

/* ---------------- Journal (attention story) ---------------- */

async function journalLoop() {
  try {
    const data = await api("/api/journal");
    if ($("xp-total")) $("xp-total").textContent = data.total_xp + " XP";
    const tl = $("timeline");
    if (!tl) return;
    tl.innerHTML = "";
    (data.timeline || []).forEach((e) => {
      const li = document.createElement("li");
      li.className = `k-${e.kind}` + (e.state ? ` state-${e.state}` : "");
      // model-written summaries and saved user messages render as text
      const hl = document.createElement("div");
      hl.className = "hl";
      hl.textContent = e.headline;
      const dt = document.createElement("div");
      dt.className = "dt";
      dt.textContent = e.detail || "";
      const t = document.createElement("div");
      t.className = "t";
      t.textContent = fmtTime(e.ts);
      li.append(hl, dt, t);
      tl.appendChild(li);
    });
    if (!(data.timeline || []).length) {
      tl.innerHTML = "<li><i>an empty story — start watching from the HUD</i></li>";
    }
  } catch (_) {}
}

/* ---------------- Gate ---------------- */

function gateMsg(text, me) {
  const chat = $("chat");
  const div = document.createElement("div");
  div.className = "msg " + (me ? "me" : "sys");
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

/* Negotiation speed varies by machine and model, so show elapsed time without
   promising a response deadline. */
function gatePending() {
  const chat = $("chat");
  const div = document.createElement("div");
  div.className = "msg sys pending";
  div.setAttribute("aria-live", "off"); // a 1s counter must not spam a reader
  const label = document.createElement("span");
  label.textContent = "waiting for the model response";
  const clock = document.createElement("span");
  clock.className = "elapsed";
  clock.textContent = "0s";
  div.append(label, clock);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;

  const start = Date.now();
  const timer = setInterval(() => {
    const secs = Math.round((Date.now() - start) / 1000);
    clock.textContent = secs + "s";
    if (secs >= 15 && !label.dataset.slow) {
      label.dataset.slow = "1";
      label.textContent = "still waiting — response time depends on your model and machine";
      chat.scrollTop = chat.scrollHeight;
    }
  }, 1000);
  return {
    remove() {
      clearInterval(timer);
      div.remove();
    },
  };
}

function renderGateState(s) {
  const latest = s.recent_verdicts && s.recent_verdicts[0];
  const active = (s.goals || []).find((g) => !g.done);
  if ($("gate-strictness")) $("gate-strictness").textContent = s.strictness;
  if ($("gate-threshold")) {
    $("gate-threshold").textContent = `${s.drift_streak} / ${s.drift_threshold} consecutive checks`;
  }
  if ($("gate-intro-copy")) {
    $("gate-intro-copy").textContent = s.gate_open
      ? `The app opened this check after ${s.drift_streak} consecutive drift classifications met the ${s.strictness} threshold. Review the reports and tell Pip what changed.`
      : "This page is available, but there is no active drift gate right now. You can still review recent reports or speak with Pip.";
  }
  if ($("gate-goal")) $("gate-goal").textContent = active ? active.title : "No active mission";
  if ($("gate-goal-meta")) $("gate-goal-meta").textContent = active
    ? `${active.minutes} minute focus block · ${active.difficulty} effort`
    : "Add or update a mission in the workspace.";
  setPipFace(latest ? latest.state : "unknown");
  if ($("mascot-line") && !$("mascot-line").dataset.busy) {
    $("mascot-line").textContent = s.gate_open
      ? "The recent classifications are here. They can be wrong; tell me what you think happened."
      : "There isn’t an active gate. We can still look at the latest reports together.";
  }
  const evidence = $("gate-evidence");
  if (!evidence) return;
  evidence.innerHTML = "";
  (s.recent_verdicts || []).slice(0, 5).forEach((v) => {
    const li = document.createElement("li");
    const meta = document.createElement("div");
    meta.className = "evidence-meta";
    const state = document.createElement("span");
    state.className = "s-" + v.state;
    state.textContent = v.state.replace("_", " ");
    const time = document.createElement("time");
    time.textContent = fmtTime(v.ts);
    li.appendChild(meta);
    meta.append(state, time);
    const summary = document.createElement("p");
    summary.textContent = v.summary || "No summary available for this classification.";
    li.appendChild(summary);
    evidence.appendChild(li);
  });
  if (!evidence.children.length) {
    const empty = document.createElement("li");
    empty.className = "empty-note";
    empty.textContent = "No screen classifications are saved yet.";
    evidence.appendChild(empty);
  }
}

async function gateInit() {
  try {
    renderGateState(await api("/api/state"));
  } catch (_) {
    if ($("mascot-line")) $("mascot-line").textContent = "I can’t load the latest reports right now. You can still send a message.";
  }
  gateMsg("I can review the latest saved classifications with you. What context should I consider?", false);
  $("say").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const box = $("say-box");
    const btn = $("say-btn");
    const text = box.value.trim();
    if (!text) return;
    gateMsg(text, true);
    box.value = "";
    box.disabled = true;
    if (btn) btn.disabled = true; // one turn in flight at a time
    if ($("mascot-line")) {
      $("mascot-line").dataset.busy = "1";
      $("mascot-line").textContent = "Sending your response to the configured model…";
    }
    const pending = gatePending();
    try {
      const out = await api("/api/negotiate", { message: text });
      pending.remove();
      gateMsg(out.message || "(the System says nothing)", false);
      if (out.chore) {
        gateMsg("PENALTY ZONE: " + out.chore, false);
        if ($("mascot-line")) $("mascot-line").textContent = "A chore was added to your list. Check the workspace for its details.";
      } else if (out.concede) {
        if ($("mascot-line")) $("mascot-line").textContent = "Pip accepted your explanation. Read the reply for what happens next.";
      } else if ($("mascot-line")) {
        $("mascot-line").textContent = "The negotiation didn’t resolve in your favor. The model’s reply has the details.";
      }
      if (out.concede) gateMsg("Negotiation outcome: accepted.", false);
      if (!out.concede && !out.chore) gateMsg("Negotiation outcome: not accepted.", false);
      try { renderGateState(await api("/api/state")); } catch (_) {}
      if ($("mascot-line")) delete $("mascot-line").dataset.busy;
    } catch (e) {
      pending.remove();
      gateMsg("The response could not be completed: " + e.message, false);
      if ($("mascot-line")) {
        delete $("mascot-line").dataset.busy;
        $("mascot-line").textContent = "I couldn’t get a response. Check the model connection or try again.";
      }
    } finally {
      box.disabled = false;
      if (btn) btn.disabled = false;
      box.focus();
    }
  });
  $("say-box").focus();
}

/* ---------------- boot ---------------- */

if (page === "hud") hudInit();
if (page === "gate") gateInit();
if (page === "journal") { journalLoop(); setInterval(journalLoop, 4000); }
