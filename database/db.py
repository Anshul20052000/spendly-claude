"""SQLite helpers for the Spendly data layer.

Exposes:
    get_db()   — returns a sqlite3 connection with row_factory and FK enforcement
    init_db()  — creates users and expenses tables (idempotent)
    seed_db()  — inserts demo user and 8 sample expenses (idempotent)
"""

import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

# Project root is the parent of the database package.
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "expense_tracker.db"

DEMO_USER = {
    "name": "Demo User",
    "email": "demo@spendly.com",
    "password": "demo123",
}

# 8 sample expenses spanning June 2026, covering all 7 fixed categories.
# (amount, category, date, description)
SAMPLE_EXPENSES = [
    (450.00, "Food", "2026-06-02", "Lunch at Saravana Bhavan"),
    (120.50, "Transport", "2026-06-05", "Uber to office"),
    (1850.00, "Bills", "2026-06-08", "Electricity bill"),
    (320.00, "Health", "2026-06-10", "Pharmacy — vitamins"),
    (650.00, "Entertainment", "2026-06-14", "Movie tickets (PVR)"),
    (1499.00, "Shopping", "2026-06-18", "Amazon — earphones"),
    (80.00, "Other", "2026-06-22", "Stationery"),
    (275.00, "Health", "2026-06-26", "Gym day pass"),
]


def get_db():
    """Return a SQLite connection with row_factory and FK enforcement enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db=None):
    """Create users and expenses tables if they do not already exist."""
    owns_conn = db is None
    conn = db if db is not None else get_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                description TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def seed_db(db=None):
    """Insert the demo user and 8 sample expenses exactly once."""
    owns_conn = db is None
    conn = db if db is not None else get_db()
    try:
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing:
            return  # already seeded — prevent duplicates

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (
                DEMO_USER["name"],
                DEMO_USER["email"],
                generate_password_hash(DEMO_USER["password"]),
            ),
        )
        demo_user_id = cursor.lastrowid

        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(demo_user_id, amt, cat, dt, desc) for amt, cat, dt, desc in SAMPLE_EXPENSES],
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def create_user(name, email, password_hash):
    """Insert a new user into the database.
    Returns the new user's id.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_by_email(email):
    """Look up a user by email. Returns a Row or None."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()
