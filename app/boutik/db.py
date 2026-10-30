"""SQLite storage. One shop per instance; the shop owns its node and its data."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  emoji TEXT NOT NULL DEFAULT '',
  price_xof INTEGER NOT NULL CHECK (price_xof > 0),
  active INTEGER NOT NULL DEFAULT 1
);
-- A payment = a sale at the counter or an ardoise (credit) settled later.
CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY,
  token TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('sale','credit')),
  amount_xof INTEGER NOT NULL CHECK (amount_xof > 0),
  items TEXT NOT NULL DEFAULT '[]',
  customer TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','paid','cancelled')),
  method TEXT NOT NULL DEFAULT '' CHECK (method IN ('','lightning','cash')),
  created_at INTEGER NOT NULL,
  paid_at INTEGER,
  r_hash TEXT,
  bolt11 TEXT,
  amount_sats INTEGER,
  invoice_expires_at INTEGER,
  prev_r_hash TEXT
);
CREATE INDEX IF NOT EXISTS payments_created ON payments(created_at);
CREATE INDEX IF NOT EXISTS payments_status ON payments(status, kind);
CREATE TABLE IF NOT EXISTS sends (
  id INTEGER PRIMARY KEY,
  amount_sats INTEGER NOT NULL,
  amount_xof INTEGER NOT NULL,
  fee_sat INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
"""

DEMO_PRODUCTS = [
    ("Pain", "🥖", 150),
    ("Riz 1 kg", "🍚", 500),
    ("Sucre 1 kg", "🍬", 700),
    ("Huile 1 L", "🛢", 1300),
    ("Lait sachet", "🥛", 250),
    ("Café Touba", "☕", 100),
    ("Savon", "🧼", 300),
    ("Eau 1,5 L", "💧", 400),
]


class DB:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(payments)")}
        if "prev_r_hash" not in cols:
            # Invoice replaced in its last minute: still payable, so keep tracking it.
            self.conn.execute("ALTER TABLE payments ADD COLUMN prev_r_hash TEXT")

    def q(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def exec(self, sql: str, params: tuple | dict = ()) -> int:
        cur = self.conn.execute(sql, params)
        return cur.lastrowid or cur.rowcount

    # settings
    def get_setting(self, key: str) -> str | None:
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.exec(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def seed_products(self) -> None:
        if self.one("SELECT 1 FROM products LIMIT 1"):
            return
        for name, emoji, price in DEMO_PRODUCTS:
            self.exec("INSERT INTO products(name,emoji,price_xof) VALUES(?,?,?)", (name, emoji, price))


def payment_dict(row: sqlite3.Row, public: bool = False) -> dict[str, Any]:
    d = {
        "id": row["id"],
        "token": row["token"],
        "kind": row["kind"],
        "amount_xof": row["amount_xof"],
        "items": json.loads(row["items"]),
        "customer": row["customer"],
        "note": row["note"],
        "status": row["status"],
        "method": row["method"],
        "created_at": row["created_at"],
        "paid_at": row["paid_at"],
        "bolt11": row["bolt11"] if row["status"] == "open" else None,
        "amount_sats": row["amount_sats"],
        "invoice_expires_at": row["invoice_expires_at"],
    }
    if public:
        # The customer-facing page only needs what to pay, not the shop's records.
        for k in ("id", "note", "created_at"):
            d.pop(k)
    return d


def now() -> int:
    return int(time.time())
