"""SQLite storage for platform accounts, transactions and network samples."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL,
    private_key TEXT NOT NULL,
    kind TEXT NOT NULL,              -- 'history' or 'new'
    history_wallet TEXT,             -- real Ethereum wallet whose history is scored
    risk_score REAL,                 -- NULL for a new wallet
    tier INTEGER NOT NULL,
    topups INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    value_eth REAL NOT NULL,
    mode TEXT NOT NULL,              -- 'plain' (DoomForge off) or 'doomforge'
    tier INTEGER,
    risk_score REAL,
    scheme TEXT,
    gas_used INTEGER,
    tx_hash TEXT,
    status INTEGER,
    details TEXT
);
CREATE TABLE IF NOT EXISTS network (
    ts INTEGER PRIMARY KEY,          -- unix time the sample was taken
    block_number INTEGER,
    block_time_s REAL,
    tx_count INTEGER,
    gas_used_ratio REAL,             -- 0..1, how full the latest block was
    base_fee_gwei REAL,
    safe_gwei REAL,
    propose_gwei REAL,
    fast_gwei REAL
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- accounts
def create_account(name, address, private_key, kind, history_wallet, risk_score, tier) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO accounts (name, address, private_key, kind, history_wallet, risk_score, tier, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, address, private_key, kind, history_wallet, risk_score, tier, time.time()),
        )
        return cur.lastrowid


def get_account(account_id: int):
    with connect() as c:
        return c.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()


def get_account_by_name(name: str):
    with connect() as c:
        return c.execute("SELECT * FROM accounts WHERE name = ?", (name,)).fetchone()


def list_accounts():
    with connect() as c:
        return c.execute("SELECT * FROM accounts ORDER BY created_at DESC").fetchall()


def add_topup(account_id: int) -> None:
    with connect() as c:
        c.execute("UPDATE accounts SET topups = topups + 1 WHERE id = ?", (account_id,))


# ------------------------------------------------------------ transactions
def record_transaction(account_id, sender, recipient, value_eth, mode, tier, risk_score,
                       scheme, gas_used, tx_hash, status, details: dict) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO transactions (account_id, created_at, sender, recipient, value_eth, mode, tier, "
            "risk_score, scheme, gas_used, tx_hash, status, details) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (account_id, time.time(), sender, recipient, value_eth, mode, tier, risk_score,
             scheme, gas_used, tx_hash, status, json.dumps(details)),
        )


def list_transactions(account_id: int | None = None):
    with connect() as c:
        if account_id is None:
            return c.execute("SELECT * FROM transactions ORDER BY created_at DESC").fetchall()
        return c.execute(
            "SELECT * FROM transactions WHERE account_id = ? ORDER BY created_at DESC", (account_id,)
        ).fetchall()


# ----------------------------------------------------------------- network
def save_network_sample(sample: dict) -> None:
    with connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO network (ts, block_number, block_time_s, tx_count, gas_used_ratio, "
            "base_fee_gwei, safe_gwei, propose_gwei, fast_gwei) VALUES "
            "(:ts, :block_number, :block_time_s, :tx_count, :gas_used_ratio, :base_fee_gwei, "
            ":safe_gwei, :propose_gwei, :fast_gwei)",
            sample,
        )


def network_samples(until_ts: int, since_ts: int):
    with connect() as c:
        return c.execute(
            "SELECT * FROM network WHERE ts <= ? AND ts >= ? ORDER BY ts", (until_ts, since_ts)
        ).fetchall()


def network_sample_count() -> tuple[int, int | None, int | None]:
    with connect() as c:
        row = c.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM network").fetchone()
        return row[0], row[1], row[2]
