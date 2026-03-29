# Client Signal Notifier POC

A local Python Proof of Concept (POC) that fetches clients via a local FastAPI server, scrapes news using DuckDuckGo, classifies market signals using dynamically configurable rules via Azure OpenAI, and exports owner notifications to an Excel file.

## Architecture

```
classification_rules.json   ← Edit to change P1/P2/P3 criteria
         │
         ▼
     main.py  ──→  client_api.py (FastAPI, port 8000)
         │               │
         │          signals.db (SQLite)
         │
         ├──→  DuckDuckGo news scraper
         ├──→  Azure OpenAI (market summary + signal classification)
         └──→  owner_notifications.xlsx
```

### Components

| File | Purpose |
|------|---------|
| `database.py` | SQLite schema setup; seeds 10 dummy clients |
| `client_api.py` | FastAPI mock CRM API – `GET /clients` |
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
- `GET /clients/{id}` – get a single client
- `GET /health` – health check
- `GET /docs` – Swagger UI