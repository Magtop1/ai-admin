"""Хранилище на SQLite: сессии диалога, сообщения и пойманные заявки.

Никакой внешней базы, файл рядом с приложением. Этого хватает и для демо,
и для первого клиента: заявки видно в админке, выгрузка в CSV одной кнопкой.
"""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "leads.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    niche TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    niche TEXT NOT NULL,
    name TEXT,
    phone TEXT,
    question TEXT,
    quote TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_niche ON leads(niche);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def get_session(con: sqlite3.Connection, sid: str, niche: str) -> dict:
    row = con.execute("SELECT state FROM sessions WHERE id = ?", (sid,)).fetchone()
    if row:
        return json.loads(row["state"])
    state = {"stage": "start", "service": None, "qty": None, "urgent": False, "name": None}
    con.execute(
        "INSERT INTO sessions (id, niche, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (sid, niche, json.dumps(state), _now(), _now()),
    )
    con.commit()
    return state


def save_session(con: sqlite3.Connection, sid: str, state: dict) -> None:
    con.execute(
        "UPDATE sessions SET state = ?, updated_at = ? WHERE id = ?",
        (json.dumps(state, ensure_ascii=False), _now(), sid),
    )
    con.commit()


def log_message(con: sqlite3.Connection, sid: str, role: str, text: str) -> None:
    con.execute(
        "INSERT INTO messages (session_id, role, text, created_at) VALUES (?, ?, ?, ?)",
        (sid, role, text, _now()),
    )
    con.commit()


def add_lead(con, sid: str, niche: str, name: str | None, phone: str | None, question: str, quote: dict | None) -> int:
    cur = con.execute(
        "INSERT INTO leads (session_id, niche, name, phone, question, quote, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sid, niche, name, phone, question, json.dumps(quote, ensure_ascii=False) if quote else None, _now()),
    )
    con.commit()
    return int(cur.lastrowid)


def leads(con, niche: str | None = None, limit: int = 200) -> list[dict]:
    q = "SELECT * FROM leads"
    args: list = []
    if niche:
        q += " WHERE niche = ?"
        args.append(niche)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in con.execute(q, args).fetchall()]


def leads_csv(con) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["id", "ниша", "имя", "телефон", "вопрос", "смета", "когда"])
    for r in leads(con, limit=10_000):
        w.writerow([r["id"], r["niche"], r["name"] or "", r["phone"] or "", r["question"] or "", r["quote"] or "", r["created_at"]])
    return buf.getvalue()


def stats(con) -> dict:
    row = con.execute("SELECT COUNT(*) AS n FROM leads").fetchone()
    sessions = con.execute("SELECT COUNT(DISTINCT session_id) AS n FROM messages").fetchone()
    with_phone = con.execute("SELECT COUNT(*) AS n FROM leads WHERE phone IS NOT NULL AND phone != ''").fetchone()
    return {"leads": row["n"], "sessions": sessions["n"], "with_phone": with_phone["n"]}
