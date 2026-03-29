"""
client_api.py - Mock CRM API built with FastAPI.

Exposes a single endpoint:
  GET /clients  →  list of all clients from signals.db

Run with:
  uvicorn client_api:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

import database  # initialises DB on import

app = FastAPI(title="Mock CRM API", version="1.0.0")

# Ensure the DB and tables exist when the API server starts.
database.init_db()


class Client(BaseModel):
    id: int
    name: str
    owner_name: str


@app.get("/clients", response_model=List[Client], summary="List all clients")
def list_clients():
    """Return every client stored in signals.db."""
    conn = database.get_connection()
    try:
        rows = conn.execute("SELECT id, name, owner_name FROM clients").fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No clients found in database.")
        return [Client(id=r["id"], name=r["name"], owner_name=r["owner_name"]) for r in rows]
    finally:
        conn.close()


@app.get("/clients/{client_id}", response_model=Client, summary="Get a specific client")
def get_client(client_id: int):
    """Return a single client by ID."""
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, owner_name FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found.")
        return Client(id=row["id"], name=row["name"], owner_name=row["owner_name"])
    finally:
        conn.close()


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok"}
