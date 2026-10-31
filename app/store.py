"""Local SQLite store. The only persistence layer.

Premise 4 compliance: everything stays on the user's device, is inspectable
and deletable in one call (`Store.delete_all_history()`).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
  goal_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  title      TEXT NOT NULL,
  minutes    INTEGER NOT NULL DEFAULT 30,
  difficulty TEXT NOT NULL DEFAULT 'easy',
  done       INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS frames (
  frame_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       REAL NOT NULL,
  label    TEXT NOT NULL DEFAULT '',
  hash     TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS verdicts (
  verdict_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  frame_id    INTEGER NOT NULL,
  ts          REAL NOT NULL,
  state       TEXT NOT NULL,
  summary     TEXT NOT NULL DEFAULT '',
  confidence  REAL NOT NULL DEFAULT 0.0,
  category    TEXT NOT NULL DEFAULT '',
  provider    TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS decisions (
  decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          REAL NOT NULL,
  action      TEXT NOT NULL,
  message     TEXT NOT NULL DEFAULT '',
  xp_awarded  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS xp (
  xp_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  ts     REAL NOT NULL,
  amount INTEGER NOT NULL,
  reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS chores (
  chore_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL,
  reason      TEXT NOT NULL DEFAULT '',
  assigned_at REAL NOT NULL,
  done        INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS negotiations (
  negotiation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      REAL NOT NULL,
  mode    TEXT NOT NULL DEFAULT 'medium',
  user    TEXT NOT NULL DEFAULT '',
  conceded INTEGER NOT NULL DEFAULT 1,
  reply   TEXT NOT NULL DEFAULT '',
  chore   TEXT NOT NULL DEFAULT ''
);
"""


class Store:
    def __init__(self, path: str | Path = "./data/letshack.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # -- goals --

    def add_goal(self, title: str, minutes: int = 30, difficulty: str = "easy") -> int:
        cur = self.conn.execute(
            "INSERT INTO goals (title, minutes, difficulty, created_at) VALUES (?,?,?,?)",
            (title, minutes, difficulty, time.time()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def goals(self, include_done: bool = True) -> list[dict[str, Any]]:
        q = "SELECT * FROM goals" + ("" if include_done else " WHERE done=0")
        return [dict(r) for r in self.conn.execute(q)]

    def set_goal_done(self, goal_id: int, done: bool = True) -> None:
        self.conn.execute(
            "UPDATE goals SET done=? WHERE goal_id=?", (int(done), goal_id)
        )
        self.conn.commit()

    # -- frames / verdicts --

    def add_frame(self, ts: float, label: str = "", hash: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO frames (ts, label, hash) VALUES (?,?,?)",
            (ts, label, hash),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_verdict(
        self,
        frame_id: int,
        ts: float,
        state: str,
        summary: str = "",
        confidence: float = 0.0,
        category: str = "",
        provider: str = "",
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO verdicts (frame_id, ts, state, summary, confidence, category,"
            " provider) VALUES (?,?,?,?,?,?,?)",
            (frame_id, ts, state, summary, confidence, category, provider),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def verdicts(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM verdicts ORDER BY verdict_id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    def drifts(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT ts, summary, category FROM verdicts WHERE state='drift'"
            " ORDER BY verdict_id DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    # -- decisions / xp --

    def add_decision(self, ts: float, action: str, message: str = "", xp: int = 0) -> None:
        self.conn.execute(
            "INSERT INTO decisions (ts, action, message, xp_awarded) VALUES (?,?,?,?)",
            (ts, action, message, xp),
        )
        self.conn.commit()

    def xp_add(self, amount: int, reason: str = "") -> None:
        self.conn.execute(
            "INSERT INTO xp (ts, amount, reason) VALUES (?,?,?)",
            (time.time(), amount, reason),
        )
        self.conn.commit()

    def xp_total(self) -> int:
        row = self.conn.execute("SELECT COALESCE(SUM(amount),0) AS total FROM xp").fetchone()
        return int(row["total"])

    # -- chores (penalty zone) --

    def assign_chore(self, title: str, reason: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO chores (title, reason, assigned_at) VALUES (?,?,?)",
            (title, reason, time.time()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def open_chores(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM chores WHERE done=0")]

    # -- negotiations (case file) --

    def add_negotiation(
        self, mode: str, user: str, conceded: bool, reply: str, chore: str = ""
    ) -> None:
        self.conn.execute(
            "INSERT INTO negotiations (ts, mode, user, conceded, reply, chore)"
            " VALUES (?,?,?,?,?,?)",
            (time.time(), mode, user, int(conceded), reply, chore),
        )
        self.conn.commit()

    def negotiations(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM negotiations ORDER BY negotiation_id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    # -- privacy switch (premise 4) --

    def delete_all_history(self) -> None:
        """Wipe every observation/decision/xp/chore record. Goals survive."""
        with self.conn as c:
            for table in ("frames", "verdicts", "decisions", "xp", "chores", "negotiations"):
                c.execute(f"DELETE FROM {table}")
            c.execute("UPDATE goals SET done=0")
