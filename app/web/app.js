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

const STATE_EMOJI = {
  on_track: ["🎯", "locked in", "s-ok"],
  drift: ["⚠️", "drifting", "s-drift"],
  break: ["☕", "on break", "s-break"],
  unknown: ["❔", "unclear", "s-unknown"],
};
const STATE_EMOJI_OFF = ["😴", "watch off", "s-unknown"];
const HOST_EMOJI = {
  Engine: "🖥️", // generic
};

function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* ---------------- HUD ---------------- */

function renderAvatar(state, watchOn) {
  const [emoji, label, cls] = watchOn ? (STATE_EMOJI[state] || STATE_EMOJI.unknown) : STATE_EMOJI_OFF;
  const ring = $("xp-ring");
  if (ring) {
    ring.classList.remove("drift", "break");
    if (cls === "s-drift") ring.classList.add("drift");
    if (cls === "s-break") ring.classList.add("break");
  }
  if ($("avatar")) {
    $("avatar").textContent = emoji;
    $("avatar-state").textContent = label;
    $("avatar-state").className = "avatar-state " + cls;
  }
}

function renderState(s) {
  if ($("strictness")) $("strictness").textContent = s.strictness;
  if ($("level")) $("level").textContent = "LEVEL " + s.level;
  if ($("xp-total")) $("xp-total").textContent = s.xp_total + " XP";
  if ($("focus-streak")) {
    $("focus-streak").textContent =
      s.focus_streak > 0 ? "streak ×" + s.focus_streak : "no streak yet";
  }
  const ring = $("xp-ring");
  if (ring) {
    const pct = s.xp_level_size > 0 ? s.xp_into_level / s.xp_level_size : 0;
    ring.style.strokeDashoffset = String(327 - 327 * Math.max(0, Math.min(1, pct)));
  }
  // avatar mirrors the most recent verdict while watching
  const last = s.recent_verdicts && s.recent_verdicts[0];
  renderAvatar(last ? last.state : "unknown", s.watch_on);

  // goals
  const gl = $("goals");
  if (gl) {
    gl.innerHTML = "";
    (s.goals || []).forEach((g) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="${g.done ? "done" : ""}">${g.title}</span>
        <span class="t">${g.difficulty} · ${g.minutes}m</span>`;
      gl.appendChild(li);
    });
    if (!(s.goals || []).length) gl.innerHTML = "<li><i>no goals yet — set one</i></li>";
  }

  // evidence trail
  const tl = $("verdicts");
  if (tl) {
    tl.innerHTML = "";
    (s.recent_verdicts || []).forEach((v) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="s-${v.state}">${v.state}</span>
        <span>${v.summary || "—"}</span><span class="t">${fmtTime(v.ts)}</span>`;
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
      li.innerHTML = `<span>${c.title}</span><span class="t">${c.reason || "penalty"}</span>`;
      cl.appendChild(li);
    });
    if ($("chores-empty")) {
      $("chores-empty").style.display = (s.open_chores || []).length ? "none" : "block";
    }
  }

  const btn = $("watch-toggle");
  if (btn) {
    btn.textContent = s.watch_on ? "⏸ Stop watching" : "▶ Start watching";
  }
  if ($("gate-banner")) {
    $("gate-banner").classList.toggle("hidden", !s.gate_open);
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
      const on = wt.textContent.includes("Stop");
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
      li.innerHTML = `<div class="hl">${e.headline}</div>
        <div class="dt">${e.detail || ""}</div>
        <div class="t">${fmtTime(e.ts)}</div>`;
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

async function gateInit() {
  gateMsg("State your business. The System has the receipts.", false);
  $("say").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const box = $("say-box");
    const text = box.value.trim();
    if (!text) return;
    gateMsg(text, true);
    box.value = "";
    box.disabled = true;
    try {
      const out = await api("/api/negotiate", { message: text });
      gateMsg(out.message || "(the System says nothing)", false);
      if (out.chore) gateMsg("PENALTY ZONE: " + out.chore, false);
      if (out.concede) gateMsg("— the gate opens. Make it count. 🚪✅", false);
      if (!out.concede && !out.chore) gateMsg("— the System holds the line. 🚪⛔", false);
    } catch (e) {
      gateMsg("(System error: " + e.message + ")", false);
    } finally {
      box.disabled = false;
      box.focus();
    }
  });
  $("say-box").focus();
}

/* ---------------- boot ---------------- */

if (page === "hud") hudInit();
if (page === "gate") gateInit();
if (page === "journal") { journalLoop(); setInterval(journalLoop, 4000); }
