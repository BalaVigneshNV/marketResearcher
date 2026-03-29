"""
client_api.py - Mock CRM API built with FastAPI.

Endpoints
---------
  GET    /clients           – list all clients
  GET    /clients/{id}      – get a single client
  POST   /clients           – add a new client
  PUT    /clients/{id}      – update a client's name or owner
  DELETE /clients/{id}      – remove a client

Run with:
  uvicorn client_api:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

import database  # initialises DB on import

app = FastAPI(title="Mock CRM API", version="1.1.0")

# Ensure the DB and tables exist when the API server starts.
database.init_db()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Client(BaseModel):
    id: int
    name: str
    owner_name: str


class ClientCreate(BaseModel):
    name: str
    owner_name: str


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    owner_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@app.get("/clients", response_model=List[Client], summary="List all clients")
def list_clients():
    """Return every client stored in signals.db."""
    conn = database.get_connection()
    try:
        rows = conn.execute("SELECT id, name, owner_name FROM clients ORDER BY id").fetchall()
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


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------

@app.post("/clients", response_model=Client, status_code=201, summary="Add a new client")
def create_client(body: ClientCreate):
    """
    Add a new client.

    **body** (JSON):
    ```json
    { "name": "Acme Corp", "owner_name": "Jane Doe" }
    ```
    """
    conn = database.get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM clients WHERE name = ?", (body.name,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Client '{body.name}' already exists."
            )
        cursor = conn.execute(
            "INSERT INTO clients (name, owner_name) VALUES (?, ?)",
            (body.name, body.owner_name),
        )
        conn.commit()
        new_id = cursor.lastrowid
        return Client(id=new_id, name=body.name, owner_name=body.owner_name)
    finally:
        conn.close()


@app.put("/clients/{client_id}", response_model=Client, summary="Update a client")
def update_client(client_id: int, body: ClientUpdate):
    """
    Update a client's name and/or owner.

    **body** (JSON) – supply only the fields you want to change:
    ```json
    { "owner_name": "New Owner" }
    ```
    """
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, owner_name FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found.")
        new_name = body.name if body.name is not None else row["name"]
        new_owner = body.owner_name if body.owner_name is not None else row["owner_name"]
        conn.execute(
            "UPDATE clients SET name = ?, owner_name = ? WHERE id = ?",
            (new_name, new_owner, client_id),
        )
        conn.commit()
        return Client(id=client_id, name=new_name, owner_name=new_owner)
    finally:
        conn.close()


@app.delete("/clients/{client_id}", status_code=204, summary="Remove a client")
def delete_client(client_id: int):
    """
    Remove a client by ID.
    Associated articles are kept for historical reference.
    """
    deleted = database.remove_client(client_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found.")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

@app.get("/health", summary="Health check")
def health():
    return {"status": "ok"}
