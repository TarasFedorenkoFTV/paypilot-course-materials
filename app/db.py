"""SQLite state layer. Relational, file-backed, reset-to-seed in one call.
The test API reads these tables directly — several defects (D10, D11, D12)
are provable only against a DB row, never against the reply text."""
import json
import os
import sqlite3
from pathlib import Path

from app import config, seed

# PAYPILOT_DB lets a test run point at its own file. Without it, `pytest` and
# ci_smoke reset the database the running stand is using — measured: a dispute
# opened during a lesson disappeared when the lecturer ran the documented
# pre-lesson checks with the stand already up.
DB_PATH = (Path(os.environ["PAYPILOT_DB"]) if os.environ.get("PAYPILOT_DB")
           else config.DATA_DIR / "paypilot.db")

SCHEMA = """
CREATE TABLE customers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
    tier TEXT NOT NULL, compliance_hold INTEGER NOT NULL DEFAULT 0,
    fx_allowance_used_eur REAL NOT NULL DEFAULT 0);
CREATE TABLE accounts (
    id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
    currency TEXT NOT NULL, balance REAL NOT NULL);
CREATE TABLE transactions (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
    date TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL,
    merchant TEXT NOT NULL, direction TEXT NOT NULL,
    transfer_type TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE disputes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL, account_id TEXT NOT NULL,
    reason_code TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL);
CREATE TABLE statements_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL, sent_to TEXT NOT NULL,
    period TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
"""

STATE_TABLES = ("customers", "accounts", "transactions", "disputes",
                "statements_sent", "escalations")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def reset() -> dict:
    """Drop everything and re-seed. The one-command return to the initial state."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = connect()
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", seed.CUSTOMERS)
    conn.executemany("INSERT INTO accounts VALUES (?,?,?,?)", seed.ACCOUNTS)
    conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?)",
                     seed.TRANSACTIONS)
    conn.commit()
    conn.close()
    return {"seed_version": seed.SEED_VERSION,
            "customers": len(seed.CUSTOMERS),
            "accounts": len(seed.ACCOUNTS),
            "transactions": len(seed.TRANSACTIONS)}


def ensure_seeded() -> None:
    if not DB_PATH.exists():
        reset()


def rows(query: str, params: tuple = ()) -> list[dict]:
    conn = connect()
    try:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def one(query: str, params: tuple = ()) -> dict | None:
    result = rows(query, params)
    return result[0] if result else None


def execute(query: str, params: tuple = ()) -> int:
    conn = connect()
    try:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.lastrowid or cur.rowcount
    finally:
        conn.close()


def table_dump(table: str) -> list[dict]:
    if table not in STATE_TABLES:
        raise ValueError(f"Unknown table {table!r}; known: {STATE_TABLES}")
    return rows(f"SELECT * FROM {table}")  # noqa: S608 — table name whitelisted above
