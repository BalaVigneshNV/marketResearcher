# Market Researcher

A comprehensive market research system that uses LangGraph to orchestrate intelligent web research with a 4-agent workflow. The system searches the web, extracts content, analyzes information, and generates detailed market research reports with citations.

## 🏗️ Architecture

The system uses **LangGraph** for stateful workflow orchestration with 4 specialized agents:

```
Client + Topic
     │
     ▼
┌─────────────────────────────────────────────────┐
│          LangGraph Workflow                     │
│                                                 │
│  1. Planner                                     │
│     → Generates subtopics, search queries,      │
│       source preferences, and report outline    │
│                                                 │
│  2. Researcher                                  │
│     → Web search (DuckDuckGo/SearXNG)          │
│     → Page fetching (requests → Playwright)     │
│     → Content extraction (Trafilatura)          │
│                                                 │
│  3. Analyst                                     │
│     → Extracts structured facts:                │
│       • claim, metric, company, geography       │
│       • date, source, evidence snippet          │
│                                                 │
│  4. Writer                                      │
│     → Compiles final report with citations      │
│     → Generates executive summary               │
│                                                 │
└─────────────────────────────────────────────────┘
     │
     ▼
Market Research Report (Markdown)
+ Structured Facts Database (SQLite)
```

## 🎯 Features

- **Deterministic 4-agent workflow** using LangGraph
- **Intelligent web scraping** with fallback strategies:
  - Primary: `requests` for fast, simple pages
  - Fallback: `Playwright` for JavaScript-heavy pages
- **Advanced content extraction** with Trafilatura
- **Structured fact extraction** with OpenAI
- **Full-text search** using SQLite FTS5
- **Comprehensive reports** with proper citations
- **Ready for vector retrieval**: FAISS and Qdrant support included

## 📦 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

For Playwright support (needed for JavaScript-heavy websites):

```bash
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your OpenAI API key
```

Required variables in `.env`:

```
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 3. Run market research

#### For a single client:

```bash
python orchestrator.py --client "Tesla Inc."
```

#### For a specific topic:

```bash
python orchestrator.py --client "Apple Inc." --topic "AI Product Strategy Analysis"
```

#### For all clients:

```bash
python orchestrator.py --all
```

#### List available clients:

```bash
python orchestrator.py --list-clients
```

### 4. View results

The system generates:
- **Markdown report**: `report_<ClientName>_<SessionID>.md`
- **Database records**: Stored in `market_research.db` with:
  - Research sessions
  - Raw evidence from web sources
  - Structured facts with metadata
  - Final reports

You can query the database directly:

```python
import database_v2

# Get all facts for a session
facts = database_v2.get_structured_facts(session_id=1)

# Full-text search across facts
results = database_v2.search_facts("revenue growth")

# Get the final report
report = database_v2.get_report(session_id=1)
```

## 🧠 Agent Details

### 1. Planner Agent

**Purpose**: Create a comprehensive research plan

**Inputs**:
- Client name
- Research topic

**Outputs**:
- Subtopics to investigate (5-7 key areas)
- Search queries (10-15 targeted queries)
- Source preferences (preferred domains/types)
- Report outline (structured markdown template)

**Implementation**: `agents/planner.py`

### 2. Researcher Agent

**Purpose**: Gather evidence from the web

**Process**:
1. Execute search queries via DuckDuckGo
2. Fetch pages using `requests` (fast)
3. Fall back to `Playwright` for JS-heavy sites
4. Extract clean text with `Trafilatura`
5. Store raw evidence in database

**Outputs**:
- Raw evidence records with full content
- Metadata (source, fetch method, timestamps)

**Implementation**: `agents/researcher.py`

### 3. Analyst Agent

**Purpose**: Extract structured facts from raw evidence

**Process**:
1. Analyze each piece of evidence with OpenAI
2. Extract structured data points:
   - **Claim**: Factual statement
   - **Metric**: Quantifiable data
   - **Company**: Company name
   - **Geography**: Region/location
   - **Date**: Time reference
   - **Evidence snippet**: Supporting quote
   - **Fact type**: Category (financial, product_launch, partnership, etc.)
   - **Confidence**: 0.0-1.0

**Outputs**:
- Structured facts in database
- Full-text searchable via SQLite FTS

**Implementation**: `agents/analyst.py`

### 4. Writer Agent

**Purpose**: Compile final market research report

**Process**:
1. Organize facts by type
2. Follow report outline from Planner
3. Generate comprehensive markdown report
4. Include proper citations with source URLs
5. Create executive summary

**Outputs**:
- Final markdown report
- Executive summary
- Saved to file and database

**Implementation**: `agents/writer.py`

## 🗄️ Database Schema

The system uses SQLite with the following tables:

- **clients**: Company names and account owners
- **research_sessions**: Each research workflow run
- **raw_evidence**: Web pages and extracted content
- **structured_facts**: Analyzed data points with metadata
- **structured_facts_fts**: Full-text search index (FTS5)
- **reports**: Final markdown reports

See `database_v2.py` for full schema and API.

## 📊 Managing Clients

### Add a client

```python
import database_v2
client_id = database_v2.add_client("Acme Corp", "Jane Doe")
```

### List clients

```python
clients = database_v2.list_clients()
for c in clients:
    print(f"{c['name']} (Owner: {c['owner_name']})")
```

### Using clients.csv (legacy)

You can still manage clients via `clients.csv`:

```csv
name,owner_name
Tesla Inc.,Alice Johnson
Apple Inc.,Bob Smith
```

Then run:

```bash
python database_v2.py
```

## 🔧 Advanced Usage

### Custom search queries

Modify the Planner agent's output by editing `agents/planner.py` to adjust the query generation strategy.

### Using Playwright by default

Edit `agents/researcher.py` and set `use_playwright=True` in `fetch_and_extract()` calls.

### Adding vector retrieval

The system includes FAISS and Qdrant in dependencies. To implement vector search:

1. Generate embeddings for `structured_facts.claim`
2. Store vectors in FAISS/Qdrant
3. Query for semantic similarity

Example skeleton:

```python
from langchain_openai import OpenAIEmbeddings
import faiss

embeddings = OpenAIEmbeddings()

# Generate embeddings for facts
fact_texts = [fact["claim"] for fact in facts]
vectors = embeddings.embed_documents(fact_texts)

# Create FAISS index
index = faiss.IndexFlatL2(len(vectors[0]))
index.add(vectors)

# Query
query_vector = embeddings.embed_query("revenue growth")
distances, indices = index.search(query_vector, k=5)
```

## 🧪 Testing Individual Agents

Each agent can be tested standalone:

```bash
# Test Planner
python agents/planner.py

# Test Researcher
python agents/researcher.py

# Test Analyst
python agents/analyst.py

# Test Writer
python agents/writer.py
```

## 📁 Project Structure

```
marketResearcher/
├── orchestrator.py              # Main entry point
├── langgraph_workflow.py        # LangGraph workflow definition
├── database_v2.py               # Enhanced database schema
├── agents/
│   ├── __init__.py
│   ├── planner.py              # Stage 1: Research planning
│   ├── researcher.py           # Stage 2: Web scraping
│   ├── analyst.py              # Stage 3: Fact extraction
│   └── writer.py               # Stage 4: Report generation
├── requirements.txt            # Dependencies
├── .env.example                # Configuration template
├── clients.csv                 # Client list (optional)
└── README.md                   # This file

# Legacy files (still functional)
├── main.py                     # Old Azure OpenAI version
├── database.py                 # Old schema
├── client_api.py               # FastAPI server
└── manage_clients.py           # Client management CLI
```

## 🔄 Migration from Old System

The old system (`main.py`) is still functional but deprecated. To migrate:

1. **Old system**: Used Azure OpenAI, simple classification (P1-P5), Excel output
2. **New system**: Uses OpenAI API, 4-agent workflow, structured facts, markdown reports

Both can coexist. The new system uses `market_research.db` while the old uses `signals.db`.

## 🛠️ Troubleshooting

### "Playwright browser not installed"

Run:
```bash
playwright install chromium
```

### "OPENAI_API_KEY not set"

Make sure you've copied `.env.example` to `.env` and added your API key.

### Search returns no results

DuckDuckGo has rate limits. If you see errors, add delays between queries or use a SearXNG instance.

### Out of memory during long research

The system processes all evidence in memory. For large-scale research, consider:
- Reducing `MAX_RESULTS_PER_QUERY` in `agents/researcher.py`
- Processing clients one at a time instead of using `--all`

## 🚀 Roadmap

- [ ] SearXNG integration for enterprise search
- [ ] Vector retrieval with FAISS/Qdrant
- [ ] Web UI for viewing reports
- [ ] Incremental research (resume sessions)
- [ ] Export to PDF/DOCX
- [ ] Multi-language support
- [ ] Scheduled automatic research runs

## 📝 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

## 📧 Contact

For questions or issues, please open a GitHub issue.
