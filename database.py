"""
database.py - SQLite database initialisation for Client Signal Notifier POC.

Creates the `clients` and `articles` tables and seeds a set of dummy clients
so the rest of the application has data to work with immediately.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "signals.db")

# ---------------------------------------------------------------------------
# Dummy clients used to seed the database on first run
# ---------------------------------------------------------------------------
DUMMY_CLIENTS = [
    (1, "Tesla Inc.", "Alice Johnson"),
    (2, "Apple Inc.", "Bob Smith"),
    (3, "Microsoft Corporation", "Carol Williams"),
    (4, "Amazon.com Inc.", "David Brown"),
    (5, "Alphabet Inc.", "Eve Davis"),
    (6, "Meta Platforms Inc.", "Frank Miller"),
    (7, "NVIDIA Corporation", "Grace Wilson"),
    (8, "Salesforce Inc.", "Henry Moore"),
    (9, "Palantir Technologies", "Ivy Taylor"),
    (10, "OpenAI", "Jack Anderson"),
]


def get_connection() -> sqlite3.Connection:
    """Return a new connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Initialise the database schema and seed dummy client data.
    Safe to call multiple times – uses IF NOT EXISTS / INSERT OR IGNORE.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # -- clients table -------------------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id          INTEGER PRIMARY KEY,
            name        TEXT    NOT NULL,
            owner_name  TEXT    NOT NULL
        )
        """
    )

    # -- articles table ------------------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id       INTEGER NOT NULL,
            url             TEXT,
            title           TEXT,
            snippet         TEXT,
            signal_type     TEXT,
            market_summary  TEXT,
            notified        INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
        """
    )

    # -- seed dummy clients --------------------------------------------------
    cursor.executemany(
        "INSERT OR IGNORE INTO clients (id, name, owner_name) VALUES (?, ?, ?)",
        DUMMY_CLIENTS,
    )

    conn.commit()
    conn.close()
    print(f"[database] Initialised. DB path: {DB_PATH}")


if __name__ == "__main__":
    init_db()
    conn = get_connection()
    rows = conn.execute("SELECT * FROM clients").fetchall()
    print(f"[database] Clients in DB ({len(rows)}):")
    for row in rows:
        print(f"  id={row['id']}  name={row['name']}  owner={row['owner_name']}")
    conn.close()
