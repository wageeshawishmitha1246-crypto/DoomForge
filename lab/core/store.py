"""SQLite storage for platform accounts, transactions and network samples."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
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
    created_at REAL NOT NULL,
    pin_salt BLOB,                   -- random per-wallet salt
    pin_hash BLOB,                   -- PBKDF2-HMAC-SHA256 of the PIN (one-way; the PIN itself is never stored)
    failed_pins INTEGER NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0,
    session_token TEXT               -- random token kept in the page link so a refresh keeps you logged in
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
        _migrate(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn) -> None:
    """Add the PIN columns to a lab.db created before PINs existed."""
    have = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)")}
    for col, ddl in (("pin_salt", "BLOB"), ("pin_hash", "BLOB"),
                     ("failed_pins", "INTEGER NOT NULL DEFAULT 0"),
                     ("locked_until", "REAL NOT NULL DEFAULT 0"), ("session_token", "TEXT")):
        if col not in have:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} {ddl}")


# ---------------------------------------------------------------- PIN
PIN_ROUNDS = 200_000
MAX_PIN_TRIES = 5
LOCK_SECONDS = 60


def _hash_pin(pin: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, PIN_ROUNDS)


def check_pin_format(pin: str) -> str | None:
    """Return an error message, or None if the PIN is acceptable (4-8 digits)."""
    if not (pin.isascii() and pin.isdigit() and 4 <= len(pin) <= 8):
        return "The PIN must be 4 to 8 digits."
    return None


def verify_pin(account_id: int, pin: str) -> tuple[bool, str]:
    """Check a PIN. After MAX_PIN_TRIES wrong tries the wallet is locked for LOCK_SECONDS."""
    with connect() as c:
        row = c.execute("SELECT pin_salt, pin_hash, failed_pins, locked_until FROM accounts WHERE id = ?",
                        (account_id,)).fetchone()
        if row is None:
            return False, "Wallet not found."
        wait = row["locked_until"] - time.time()
        if wait > 0:
            return False, f"Too many wrong PINs. Try again in {int(wait) + 1} seconds."
        if row["pin_hash"] is None:
            return False, "This wallet has no PIN. Create a new wallet."
        if hmac.compare_digest(_hash_pin(pin, row["pin_salt"]), row["pin_hash"]):
            c.execute("UPDATE accounts SET failed_pins = 0, locked_until = 0 WHERE id = ?", (account_id,))
            return True, ""
        fails = row["failed_pins"] + 1
        if fails >= MAX_PIN_TRIES:
            c.execute("UPDATE accounts SET failed_pins = 0, locked_until = ? WHERE id = ?",
                      (time.time() + LOCK_SECONDS, account_id))
            return False, f"Too many wrong PINs. Locked for {LOCK_SECONDS} seconds."
        c.execute("UPDATE accounts SET failed_pins = ? WHERE id = ?", (fails, account_id))
        return False, f"Wrong PIN. {MAX_PIN_TRIES - fails} tries left."


def start_session(account_id: int) -> str:
    """Make a fresh random token for the page link (replaces any older one)."""
    token = secrets.token_urlsafe(24)
    with connect() as c:
        c.execute("UPDATE accounts SET session_token = ? WHERE id = ?", (token, account_id))
    return token


def end_session(account_id: int) -> None:
    with connect() as c:
        c.execute("UPDATE accounts SET session_token = NULL WHERE id = ?", (account_id,))


def get_account_by_token(token: str):
    if not token:
        return None
    with connect() as c:
        return c.execute("SELECT * FROM accounts WHERE session_token = ?", (token,)).fetchone()


# ---------------------------------------------------------------- accounts
def create_account(name, address, private_key, kind, history_wallet, risk_score, tier, pin: str) -> int:
    salt = os.urandom(16)
    with connect() as c:
        cur = c.execute(
            "INSERT INTO accounts (name, address, private_key, kind, history_wallet, risk_score, tier, "
            "created_at, pin_salt, pin_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, address, private_key, kind, history_wallet, risk_score, tier, time.time(),
             salt, _hash_pin(pin, salt)),
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
