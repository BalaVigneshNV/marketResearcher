# LangGraph Market Research System - How It Works

This document explains the internal workings of the LangGraph-based market research system.

## Overview

The system uses LangGraph to create a **deterministic, stateful workflow** with 4 specialized agents that work sequentially. Unlike traditional multi-agent systems with complex message passing, LangGraph provides:

- **Shared state**: All agents read from and write to a common state object
- **Deterministic flow**: Agents execute in a fixed order (Planner → Researcher → Analyst → Writer)
- **Type safety**: TypedDict state ensures consistency
- **Checkpointing**: State can be saved and resumed

## State Management

### State Definition

```python
class ResearchState(TypedDict):
    # Input
    client_id: int
    client_name: str
    topic: str
    session_id: int

    # Planner outputs
    subtopics: List[str]
    search_queries: List[str]
    source_preferences: Dict[str, Any]
    outline: str

    # Researcher outputs (accumulates)
    raw_evidence: Annotated[List[Dict[str, Any]], operator.add]

    # Analyst outputs (accumulates)
    structured_facts: Annotated[List[Dict[str, Any]], operator.add]

    # Writer outputs
    report_title: str
    report_content: str
    report_summary: str

    # Control
    current_stage: str
    error_message: str
    completed: bool
```

The `Annotated[List[Dict], operator.add]` annotation tells LangGraph to **accumulate** items instead of replacing them. This is crucial for evidence and facts that grow as the workflow progresses.

## Workflow Graph

```
START
  │
  ▼
Planner Node
  │ (reads: client_name, topic)
  │ (writes: subtopics, search_queries, source_preferences, outline)
  ▼
Researcher Node
  │ (reads: search_queries, source_preferences)
  │ (writes: raw_evidence)
  ▼
Analyst Node
  │ (reads: raw_evidence, client_name)
  │ (writes: structured_facts)
  ▼
Writer Node
  │ (reads: structured_facts, outline, topic)
  │ (writes: report_title, report_content, report_summary)
  ▼
END
```

### Node Implementation Pattern

Each node is a function that:
1. Receives the current state
2. Performs its specialized task
3. Updates relevant state fields
4. Returns the modified state

Example:
```python
def planner_node(state: ResearchState) -> ResearchState:
    state["current_stage"] = "planner"

    plan = plan_research(
        client_name=state["client_name"],
        topic=state["topic"],
    )

    state["subtopics"] = plan["subtopics"]
    state["search_queries"] = plan["search_queries"]
    # ... update other fields

    return state
```

## Agent Implementation Details

### 1. Planner Agent (`agents/planner.py`)

**Purpose**: Strategic planning

**Process**:
1. Constructs a detailed prompt with client name and topic
2. Calls OpenAI with `response_format={"type": "json_object"}` for structured output
3. Receives JSON with:
   - `subtopics`: Areas to research
   - `search_queries`: Specific queries
   - `source_preferences`: Preferred sources
   - `outline`: Report structure in markdown

**Key Features**:
- Uses low temperature (0.3) for consistent planning
- Validates JSON structure
- Provides fallback plan if API fails

**Example Output**:
```json
{
  "subtopics": [
    "Recent product launches",
    "Market position and competition",
    "Financial performance",
    "Strategic initiatives"
  ],
  "search_queries": [
    "Tesla Model Y 2024 sales",
    "Tesla vs BYD market share",
    "Tesla Q4 2024 earnings"
  ],
  "source_preferences": {
    "preferred_domains": ["reuters.com", "bloomberg.com"],
    "source_types": ["news", "research"]
  },
  "outline": "# Tesla Market Analysis\n\n## Executive Summary\n\n..."
}
```

### 2. Researcher Agent (`agents/researcher.py`)

**Purpose**: Web scraping and content extraction

**Process**:
1. For each search query:
   - Search via DuckDuckGo
   - Get top N results (URLs)
2. For each URL:
   - Try `requests.get()` first (fast, simple)
   - If fails or returns empty, try `Playwright` (handles JS)
3. Extract content with Trafilatura:
   - Clean text extraction
   - Metadata extraction (title)
   - Create snippet (first 300 chars)
4. Store in `raw_evidence` table

**Key Features**:
- **Fallback strategy**: requests → Playwright
- **Duplicate detection**: Tracks seen URLs
- **Error handling**: Continues on individual failures
- **Metadata tracking**: Records fetch method

**Trafilatura Benefits**:
- Removes navigation, ads, boilerplate
- Keeps main article content
- Handles various website structures
- Fast and lightweight

**Example Evidence Record**:
```python
{
    "id": 123,
    "url": "https://example.com/article",
    "title": "Tesla Reports Record Q4 Deliveries",
    "content": "Full article text...",
    "snippet": "Tesla announced record deliveries...",
    "fetch_method": "requests"
}
```

### 3. Analyst Agent (`agents/analyst.py`)

**Purpose**: Structure extraction from unstructured text

**Process**:
1. For each piece of evidence:
   - Truncate content to 3000 chars (token limit)
   - Send to OpenAI with structured extraction prompt
2. OpenAI extracts facts with:
   - **Claim**: Core statement
   - **Metric**: Numbers (revenue, %, counts)
   - **Company**: Entity name
   - **Geography**: Location
   - **Date**: Time reference
   - **Evidence snippet**: Supporting quote
   - **Fact type**: Category
   - **Confidence**: Reliability score
3. Store each fact in `structured_facts` table
4. Facts automatically indexed by FTS5

**Key Features**:
- **Structured output**: JSON mode for consistency
- **Metadata extraction**: Not just facts, but context
- **Confidence scoring**: Distinguishes strong vs weak claims
- **FTS indexing**: Automatic full-text search

**Example Fact**:
```json
{
  "claim": "Tesla delivered 1.8 million vehicles globally in 2023",
  "metric": "1.8 million vehicles",
  "company": "Tesla Inc.",
  "geography": "Global",
  "date": "2023",
  "evidence_snippet": "Tesla announced it delivered 1.8M vehicles in 2023, a record...",
  "fact_type": "operational_metric",
  "confidence": 0.95,
  "source_url": "https://..."
}
```

### 4. Writer Agent (`agents/writer.py`)

**Purpose**: Report synthesis

**Process**:
1. Organize facts by type (financial, product_launch, strategic, etc.)
2. Format facts with citations for prompt
3. Send to OpenAI with:
   - Report outline from Planner
   - All structured facts
   - Instructions for markdown formatting
4. Generate main report (2000-3000 words)
5. Generate separate executive summary (2-3 paragraphs)
6. Save to `reports` table and file

**Key Features**:
- **Follows outline**: Uses Planner's structure
- **Proper citations**: [Source: URL] format
- **Executive summary**: Separate, concise
- **Markdown formatting**: Clean, readable
- **Fallback content**: Basic report if API fails

**Example Report Structure**:
```markdown
# Market Research Report: Tesla Inc. - Market Analysis

## Executive Summary

Tesla continues to dominate the EV market with record deliveries...

## Financial Performance

Tesla reported $96.8B in revenue for 2023 [Source: https://...],
representing 19% YoY growth [Source: https://...].

## Product Strategy

The company launched the Cybertruck in Q4 2024 [Source: https://...]...

## Competitive Landscape

Tesla maintains a 25% global EV market share [Source: https://...]...

## Strategic Recommendations

1. Monitor competition from Chinese manufacturers
2. Capitalize on growing demand in Europe
...
```

## Database Design

### Why SQLite?

- **Embedded**: No separate server needed
- **FTS5**: Built-in full-text search
- **ACID**: Reliable transactions
- **Simple**: Single file database
- **Fast**: Sufficient for research workloads

### Tables

1. **clients**: Who to research
2. **research_sessions**: Each workflow run
3. **raw_evidence**: Original scraped content
4. **structured_facts**: Analyzed data points
5. **structured_facts_fts**: Search index
6. **reports**: Final output

### FTS5 (Full-Text Search)

The system uses SQLite's FTS5 for searching facts:

```sql
-- Search across all fact fields
SELECT * FROM structured_facts sf
JOIN structured_facts_fts fts ON sf.id = fts.rowid
WHERE structured_facts_fts MATCH 'revenue AND growth'
ORDER BY rank;
```

Benefits:
- Fast prefix/phrase search
- Relevance ranking
- No external dependencies

Future enhancement: Replace with FAISS/Qdrant for semantic search.

## Error Handling

Each agent handles errors gracefully:

1. **API failures**: Use fallback content
2. **Scraping failures**: Skip URL, continue with others
3. **Parsing failures**: Log and use defaults
4. **Workflow errors**: Store in state, complete what's possible

Example:
```python
try:
    facts = extract_facts_from_content(content, url)
except Exception as e:
    log.warning(f"Extraction failed: {e}")
    facts = []  # Continue with empty list
```

## Performance Considerations

### Bottlenecks

1. **Web scraping**: Slowest part (network I/O)
2. **LLM calls**: Second slowest (API latency)
3. **Database**: Fast (local SQLite)

### Optimizations

1. **Parallel scraping**: Could fetch multiple URLs concurrently
2. **Batch LLM calls**: Could analyze multiple evidence pieces at once
3. **Caching**: Could cache scraped content
4. **Rate limiting**: DuckDuckGo limits require throttling

### Current Limits

- `MAX_RESULTS_PER_QUERY = 3`: Limits evidence per query
- `max_tokens = 4000`: Writer output limit
- `content[:3000]`: Analyst input truncation
- `timeout = 10s`: Request timeout

## Future Enhancements

### 1. Vector Retrieval (FAISS/Qdrant)

Replace FTS with semantic search:

```python
# Generate embeddings
embeddings = OpenAIEmbeddings()
fact_vectors = embeddings.embed_documents([f["claim"] for f in facts])

# Store in FAISS
index = faiss.IndexFlatL2(dimension)
index.add(fact_vectors)

# Semantic search
query_vector = embeddings.embed_query("financial performance")
similar_facts = index.search(query_vector, k=10)
```

### 2. SearXNG Integration

Replace DuckDuckGo with self-hosted SearXNG:

```python
def search_searxng(query: str) -> List[Dict]:
    response = requests.get(
        "http://localhost:8888/search",
        params={"q": query, "format": "json"}
    )
    return response.json()["results"]
```

### 3. Incremental Research

Resume sessions instead of starting fresh:

```python
# Check if session exists
existing = database_v2.get_research_session(session_id)
if existing and existing["status"] == "in_progress":
    # Resume from last completed stage
    start_stage = existing["current_stage"]
```

### 4. Conditional Edges

Use LangGraph conditional routing:

```python
def should_use_playwright(state):
    # Check if requests failed for most URLs
    failed_count = sum(1 for e in state["raw_evidence"] if e["fetch_method"] == "requests" and not e["content"])
    return failed_count > len(state["raw_evidence"]) * 0.5

workflow.add_conditional_edges(
    "researcher",
    should_use_playwright,
    {
        True: "researcher_playwright",  # Retry with Playwright
        False: "analyst"  # Continue normally
    }
)
```

## Testing Strategy

### Unit Tests

Test each agent independently:

```python
def test_planner():
    plan = planner.plan_research("Tesla", "Market Analysis")
    assert "subtopics" in plan
    assert len(plan["search_queries"]) > 0
```

### Integration Tests

Test full workflow with mocked LLM:

```python
@mock.patch("openai.OpenAI")
def test_full_workflow(mock_openai):
    # Mock responses
    # Run workflow
    # Assert final state
```

### End-to-End Tests

Run with real APIs on test client:

```bash
python orchestrator.py --client "Test Company" --topic "Test Research"
```

## Monitoring and Logging

The system logs at each stage:

```
[INFO] Starting research for: Tesla Inc.
[INFO] [Planner] Generating research plan...
[INFO] [Researcher] Searching: Tesla Model Y 2024
[INFO] [Researcher] Found 3 results
[INFO] [Researcher] Fetching: https://example.com/article
[INFO] [Analyst] Processing: Tesla Reports Record Sales
[INFO] [Analyst]   → Fact: Tesla delivered 1.8M vehicles
[INFO] [Writer] Generating report...
[INFO] Workflow completed. Report saved to: report_Tesla_Inc_1.md
```

Add metrics:
```python
import time

start_time = time.time()
# ... workflow execution ...
duration = time.time() - start_time

log.info(f"Workflow completed in {duration:.2f}s")
log.info(f"Evidence collected: {len(state['raw_evidence'])}")
log.info(f"Facts extracted: {len(state['structured_facts'])}")
```

## Comparison: Old vs New System

| Aspect | Old System (main.py) | New System (orchestrator.py) |
|--------|---------------------|------------------------------|
| Orchestration | Sequential script | LangGraph workflow |
| LLM | Azure OpenAI | OpenAI API |
| Search | DuckDuckGo | DuckDuckGo (SearXNG ready) |
| Scraping | requests only | requests + Playwright |
| Extraction | None (raw snippets) | Trafilatura |
| Analysis | P1-P5 classification | Structured fact extraction |
| Storage | Simple articles table | Sessions + evidence + facts |
| Retrieval | SQL queries | FTS5 (FAISS/Qdrant ready) |
| Output | Excel by owner | Markdown reports |
| State | None | Full workflow state |

## Conclusion

The LangGraph-based system provides:

1. **Clear separation of concerns**: Each agent has a specific job
2. **Deterministic execution**: Predictable, debuggable flow
3. **Shared state**: No complex message passing
4. **Structured data**: Facts, not just text
5. **Extensibility**: Easy to add new agents or features
6. **Production-ready**: Error handling, logging, persistence

This architecture scales from MVP (SQLite FTS) to enterprise (FAISS/Qdrant vectors) without major refactoring.
