"""
database_v2.py - Enhanced SQLite database for LangGraph-based Market Research System.

Schema supports:
- Research sessions with topics and client associations
- Raw evidence from web sources
- Structured facts extracted by the Analyst agent
- Full-text search (FTS) for retrieval
- Final reports with citations
"""

import csv
import sqlite3
import os
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "market_research.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "clients.csv")

# ---------------------------------------------------------------------------
# Fallback sample clients
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
    """Read name/owner pairs from clients.csv."""
    clients: list[tuple[str, str]] = []
    if not os.path.exists(CSV_PATH):
        return []

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0].strip().startswith("#"):
                continue
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
    Initialize the enhanced database schema for LangGraph market research.

    Tables:
    - clients: Company names and account owners
    - research_sessions: Each research session for a client/topic
    - raw_evidence: Web pages and content fetched by Researcher
    - structured_facts: Analyzed data points from Analyst
    - structured_facts_fts: Full-text search on facts
    - reports: Final market research reports
    """
    conn = get_connection()
    cursor = conn.cursor()

    # -- clients table -------------------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            owner_name  TEXT    NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # -- research_sessions table ---------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS research_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id       INTEGER NOT NULL,
            topic           TEXT NOT NULL,
            subtopics       TEXT,  -- JSON array
            search_queries  TEXT,  -- JSON array
            outline         TEXT,  -- JSON or markdown
            status          TEXT DEFAULT 'pending',  -- pending, in_progress, completed
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at    TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
        """
    )

    # -- raw_evidence table --------------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_evidence (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL,
            url             TEXT NOT NULL,
            title           TEXT,
            content         TEXT,  -- Full extracted text
            snippet         TEXT,  -- Short summary
            source_type     TEXT,  -- 'search', 'direct', 'crawl'
            fetch_method    TEXT,  -- 'requests', 'playwright'
            metadata        TEXT,  -- JSON for additional data
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES research_sessions(id)
        )
        """
    )

    # -- structured_facts table ----------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS structured_facts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL,
            evidence_id     INTEGER,
            claim           TEXT NOT NULL,
            metric          TEXT,
            company         TEXT,
            geography       TEXT,
            date            TEXT,
            source_url      TEXT,
            evidence_snippet TEXT,
            fact_type       TEXT,  -- e.g., 'market_size', 'growth_rate', 'competitor', etc.
            confidence      REAL,  -- 0.0 to 1.0
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES research_sessions(id),
            FOREIGN KEY (evidence_id) REFERENCES raw_evidence(id)
        )
        """
    )

    # -- structured_facts_fts: Full-text search ------------------------------
    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS structured_facts_fts
        USING fts5(
            claim,
            metric,
            company,
            geography,
            evidence_snippet,
            content='structured_facts',
            content_rowid='id'
        )
        """
    )

    # Triggers to keep FTS in sync
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS structured_facts_ai
        AFTER INSERT ON structured_facts BEGIN
            INSERT INTO structured_facts_fts(rowid, claim, metric, company, geography, evidence_snippet)
            VALUES (new.id, new.claim, new.metric, new.company, new.geography, new.evidence_snippet);
        END;
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS structured_facts_ad
        AFTER DELETE ON structured_facts BEGIN
            DELETE FROM structured_facts_fts WHERE rowid = old.id;
        END;
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS structured_facts_au
        AFTER UPDATE ON structured_facts BEGIN
            DELETE FROM structured_facts_fts WHERE rowid = old.id;
            INSERT INTO structured_facts_fts(rowid, claim, metric, company, geography, evidence_snippet)
            VALUES (new.id, new.claim, new.metric, new.company, new.geography, new.evidence_snippet);
        END;
        """
    )

    # -- reports table -------------------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL,
            title           TEXT NOT NULL,
            content         TEXT NOT NULL,  -- Markdown or HTML report
            summary         TEXT,
            format          TEXT DEFAULT 'markdown',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES research_sessions(id)
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
    print(f"[database_v2] Initialized from {source}. DB path: {DB_PATH}")


# ---------------------------------------------------------------------------
# Client operations
# ---------------------------------------------------------------------------

def list_clients() -> List[Dict[str, Any]]:
    """Return all clients."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, owner_name, created_at FROM clients ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_client(client_id: int) -> Optional[Dict[str, Any]]:
    """Get a single client by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, owner_name, created_at FROM clients WHERE id = ?",
            (client_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_client(name: str, owner_name: str) -> int:
    """Add a new client."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO clients (name, owner_name) VALUES (?, ?)",
            (name, owner_name),
        )
        conn.commit()
        if cursor.lastrowid:
            return cursor.lastrowid
        row = conn.execute(
            "SELECT id FROM clients WHERE name = ?", (name,)
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Research session operations
# ---------------------------------------------------------------------------

def create_research_session(client_id: int, topic: str) -> int:
    """Create a new research session."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO research_sessions (client_id, topic, status)
            VALUES (?, ?, 'pending')
            """,
            (client_id, topic)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_research_session(
    session_id: int,
    subtopics: Optional[str] = None,
    search_queries: Optional[str] = None,
    outline: Optional[str] = None,
    status: Optional[str] = None,
) -> None:
    """Update a research session with planner outputs."""
    conn = get_connection()
    try:
        updates = []
        params = []
        if subtopics is not None:
            updates.append("subtopics = ?")
            params.append(subtopics)
        if search_queries is not None:
            updates.append("search_queries = ?")
            params.append(search_queries)
        if outline is not None:
            updates.append("outline = ?")
            params.append(outline)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            if status == 'completed':
                updates.append("completed_at = CURRENT_TIMESTAMP")

        if updates:
            params.append(session_id)
            query = f"UPDATE research_sessions SET {', '.join(updates)} WHERE id = ?"
            conn.execute(query, params)
            conn.commit()
    finally:
        conn.close()


def get_research_session(session_id: int) -> Optional[Dict[str, Any]]:
    """Get a research session by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM research_sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Raw evidence operations
# ---------------------------------------------------------------------------

def add_raw_evidence(
    session_id: int,
    url: str,
    title: str,
    content: str,
    snippet: str,
    source_type: str = 'search',
    fetch_method: str = 'requests',
    metadata: Optional[str] = None,
) -> int:
    """Add raw evidence from web scraping."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO raw_evidence
            (session_id, url, title, content, snippet, source_type, fetch_method, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, url, title, content, snippet, source_type, fetch_method, metadata)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_raw_evidence(session_id: int) -> List[Dict[str, Any]]:
    """Get all raw evidence for a session."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM raw_evidence WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Structured facts operations
# ---------------------------------------------------------------------------

def add_structured_fact(
    session_id: int,
    claim: str,
    evidence_id: Optional[int] = None,
    metric: Optional[str] = None,
    company: Optional[str] = None,
    geography: Optional[str] = None,
    date: Optional[str] = None,
    source_url: Optional[str] = None,
    evidence_snippet: Optional[str] = None,
    fact_type: Optional[str] = None,
    confidence: float = 1.0,
) -> int:
    """Add a structured fact from the Analyst."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO structured_facts
            (session_id, evidence_id, claim, metric, company, geography, date,
             source_url, evidence_snippet, fact_type, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, evidence_id, claim, metric, company, geography, date,
             source_url, evidence_snippet, fact_type, confidence)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_structured_facts(session_id: int) -> List[Dict[str, Any]]:
    """Get all structured facts for a session."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM structured_facts WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def search_facts(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Full-text search on structured facts."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT sf.*
            FROM structured_facts sf
            JOIN structured_facts_fts fts ON sf.id = fts.rowid
            WHERE structured_facts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Report operations
# ---------------------------------------------------------------------------

def add_report(
    session_id: int,
    title: str,
    content: str,
    summary: Optional[str] = None,
    format: str = 'markdown',
) -> int:
    """Add a final report."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO reports (session_id, title, content, summary, format)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, title, content, summary, format)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_report(session_id: int) -> Optional[Dict[str, Any]]:
    """Get the report for a session."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM reports WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    clients = list_clients()
    print(f"[database_v2] Clients in DB ({len(clients)}):")
    for c in clients:
        print(f"  id={c['id']}  name={c['name']}  owner={c['owner_name']}")
