"""
database.py - SQLite database initialisation for Client Signal Notifier POC.

Creates the `clients` and `articles` tables and seeds clients from clients.csv.

How clients and owners are loaded
----------------------------------
1. Edit `clients.csv` in the same directory as this file.
   The CSV has two columns (no ID needed — IDs are assigned automatically):
       name,owner_name
       Tesla Inc.,Alice Johnson
       Apple Inc.,Bob Smith
       ...
2. Run  python database.py  (or restart the app) to apply the changes.

If clients.csv is missing the built-in sample list is used as a fallback so
the application always has data to work with out of the box.
"""

import csv
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "signals.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "clients.csv")

# ---------------------------------------------------------------------------
# Fallback sample clients (used only when clients.csv does not exist)
# ---------------------------------------------------------------------------
_SAMPLE_CLIENTS = [
    ("Tesla Inc.", "Alice Johnson"),
    ("Apple Inc.", "Bob Smith"),
    ("Microsoft Corporation", "Carol Williams"),
    ("Amazon.com Inc.", "David Brown"),
    ("Alphabet Inc.", "Eve Davis"),
    ("Meta Platforms Inc.", "Frank Miller"),
    ("NVIDIA Corporation", "Grace Wilson"),
    ("Salesforce Inc.", "Henry Moore"),
    ("Palantir Technologies", "Ivy Taylor"),
    ("OpenAI", "Jack Anderson"),
]


def _load_clients_from_csv() -> list[tuple[str, str]]:
    """
    Read name/owner pairs from clients.csv.
    Comment lines (starting with #) and blank lines are skipped.
    Returns a list of (name, owner_name) tuples.
    """
    clients: list[tuple[str, str]] = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            # Skip blank lines and comment lines
            if not row or row[0].strip().startswith("#"):
                continue
            # Skip the header row
            if row[0].strip().lower() == "name":
                continue
            if len(row) < 2:
                continue
            name = row[0].strip()
            owner = row[1].strip()
            if name and owner:
                clients.append((name, owner))
    return clients


def get_connection() -> sqlite3.Connection:
    """Return a new connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Initialise the database schema and seed clients.

    Client data source (in priority order):
      1. clients.csv  — edit this file to manage your client/owner list.
      2. Built-in sample data — used as fallback when clients.csv is absent.

    Safe to call multiple times; existing rows are never overwritten.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # -- clients table -------------------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
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

    # -- seed clients --------------------------------------------------------
    if os.path.exists(CSV_PATH):
        seed_data = _load_clients_from_csv()
        source = "clients.csv"
    else:
        seed_data = _SAMPLE_CLIENTS
        source = "built-in sample data"

    cursor.executemany(
        "INSERT OR IGNORE INTO clients (name, owner_name) VALUES (?, ?)",
        seed_data,
    )

    conn.commit()
    conn.close()
    print(f"[database] Initialised from {source}. DB path: {DB_PATH}")


def add_client(name: str, owner_name: str) -> int:
    """
    Insert a new client into the database.
    Returns the new row's id, or the existing id if the name already exists.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO clients (name, owner_name) VALUES (?, ?)",
            (name, owner_name),
        )
        conn.commit()
        if cursor.lastrowid:
            return cursor.lastrowid
        # Row already existed — fetch its id
        row = conn.execute(
            "SELECT id FROM clients WHERE name = ?", (name,)
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


def remove_client(client_id: int) -> bool:
    """
    Delete a client by id. Returns True if a row was deleted, False otherwise.
    Does NOT delete associated articles (they remain for historical reference).
    """
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_clients() -> list[dict]:
    """Return all clients as a list of dicts with keys id, name, owner_name."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, owner_name FROM clients ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    clients = list_clients()
    print(f"[database] Clients in DB ({len(clients)}):")
    for c in clients:
        print(f"  id={c['id']}  name={c['name']}  owner={c['owner_name']}")
