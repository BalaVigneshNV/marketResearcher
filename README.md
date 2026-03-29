# Client Signal Notifier POC

A local Python Proof of Concept (POC) that fetches clients via a local FastAPI server, scrapes news using DuckDuckGo, classifies market signals using dynamically configurable rules via Azure OpenAI, and exports owner notifications to an Excel file.

## Architecture

```
clients.csv  ←── Edit to manage your client/owner list
     │
     ▼
database.py  ──→  signals.db (SQLite)
     │
classification_rules.json   ← Edit to change P1/P2/P3 criteria
     │
     ▼
 main.py  ──→  client_api.py (FastAPI, port 8000)
     │
     ├──→  DuckDuckGo news scraper
     ├──→  Azure OpenAI (market summary + signal classification)
     └──→  owner_notifications.xlsx
```

### Components

| File | Purpose |
|------|---------|
| `clients.csv` | **Edit this file** to add/remove clients and assign owners |
| `database.py` | SQLite schema setup; reads `clients.csv` on startup |
| `client_api.py` | FastAPI mock CRM API – full CRUD for clients |
| `manage_clients.py` | Interactive CLI to add/remove clients without editing files |
| `classification_rules.json` | Editable P1/P2/P3 classification criteria |
| `main.py` | Main orchestration script |
| `demo.py` | Standalone demo – generates Excel without Azure or internet |
| `.env.example` | Template for environment variables |
| `requirements.txt` | Python dependencies |

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

Required variables in `.env`:

```
AZURE_OPENAI_API_KEY=<your key>
AZURE_OPENAI_ENDPOINT=https://your-resource-name.cognitiveservices.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o   # replace with your deployment name
```

### 3. Run the full pipeline

```bash
python main.py
```

`main.py` automatically starts the FastAPI server in a background thread, so you don't need to run it separately.

### 4. View results

Open `owner_notifications.xlsx`. It contains:
- **All Signals** sheet – all classified articles sorted by priority (P1 → P3)
- **One sheet per owner** – filtered view for each account owner

---

## Managing the Client and Owner List

There are **three ways** to add, update, or remove clients and their assigned owners:

### Option A — Edit `clients.csv` (recommended)

Open `clients.csv` in any text editor or spreadsheet application and add or remove rows:

```csv
name,owner_name
Tesla Inc.,Alice Johnson
Apple Inc.,Bob Smith
Acme Corp,Jane Doe          ← add your own clients here
```

Then apply the changes to the database:

```bash
python database.py
```

The file is also read automatically every time `main.py` or `client_api.py` starts.

### Option B — Interactive CLI (`manage_clients.py`)

Run the interactive menu — no file editing required:

```bash
python manage_clients.py
```

```
=== Client Manager ===
  1. List clients
  2. Add a client
  3. Remove a client
  4. Export to clients.csv
  5. Quit
```

Or use non-interactive commands for scripting:

```bash
python manage_clients.py list
python manage_clients.py add "Acme Corp" "Jane Doe"
python manage_clients.py remove 3
python manage_clients.py export   # sync DB state back to clients.csv
```

### Option C — REST API (`client_api.py`)

When the server is running, use the full CRUD API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/clients` | List all clients |
| `GET` | `/clients/{id}` | Get a single client |
| `POST` | `/clients` | Add a new client |
| `PUT` | `/clients/{id}` | Update a client's name or owner |
| `DELETE` | `/clients/{id}` | Remove a client |

**Example – add a client:**
```bash
curl -X POST http://localhost:8000/clients \
     -H "Content-Type: application/json" \
     -d '{"name": "Acme Corp", "owner_name": "Jane Doe"}'
```

**Example – update owner:**
```bash
curl -X PUT http://localhost:8000/clients/1 \
     -H "Content-Type: application/json" \
     -d '{"owner_name": "New Owner"}'
```

Visit `http://localhost:8000/docs` for the interactive Swagger UI.

---

## Demo Mode (no Azure key required)

To generate a sample `owner_notifications.xlsx` without an Azure subscription or internet access:

```bash
python demo.py          # inserts sample data and exports Excel
python demo.py --reset  # clears existing articles first, then inserts fresh demo data
```

The demo includes 14 pre-classified articles (4 × P1, 5 × P2, 5 × P3) across 10 dummy clients and 10 owners.

## Dynamic Classification Rules

Edit `classification_rules.json` to change how articles are classified — no code changes needed:

```json
{
  "P1_Criteria": "Critical signals like CEO changes, major stock drops, or bankruptcies.",
  "P2_Criteria": "Significant business events like IPOs, funding rounds, strategic partnerships.",
  "P3_Criteria": "Routine news, minor product updates, or general industry noise."
}
```

## Running the CRM API standalone

```bash
uvicorn client_api:app --reload --port 8000
```

Endpoints:
- `GET /clients` – list all clients
- `POST /clients` – add a new client
- `PUT /clients/{id}` – update a client
- `DELETE /clients/{id}` – remove a client
- `GET /health` – health check
- `GET /docs` – Swagger UI