# Lead Research Agent

AI-powered lead research engine built with **LangGraph**, **Exa**, **Tavily**, and **Hunter**. Takes a natural language query like *"find top B2B electronics manufacturers in India"* and returns structured lead data with company info, decision-maker contacts, and email addresses.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-workflow-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (HTML/CSS/JS)                   │
│  Query Input → Workflow Animation → Table / JSON / Log       │
└──────────────────────────┬──────────────────────────────────┘
                           │ SSE (Server-Sent Events)
┌──────────────────────────▼──────────────────────────────────┐
│                   Flask Server (app/server.py)               │
│  POST /api/research  →  GET /api/stream/<job_id>            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              LangGraph Workflow (app/graph.py)               │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  interpret   │───▶│ create_plan  │───▶│  discover     │  │
│  │  request     │    │              │    │  companies    │  │
│  └─────────────┘    └──────────────┘    └───────┬───────┘  │
│                                                  │          │
│  ┌─────────────┐    ┌──────────────┐    ┌───────▼───────┐  │
│  │  build_lead  │◀──│  evaluate    │◀───│  find_people  │  │
│  │             │    │  evidence    │    │  (+ contacts) │  │
│  └──────┬──────┘    └──────┬───────┘    └───────────────┘  │
│         │                  │                                │
│         │         ┌────────▼────────┐                      │
│         │         │ research_missing│ (loop if incomplete) │
│         │         └─────────────────┘                      │
│         ▼                                                  │
│    Standard Lead JSON (15 fields)                          │
└────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │    Exa    │   │  Tavily   │   │  Hunter   │
    │ (search)  │   │ (search)  │   │ (email)   │
    └───────────┘   └───────────┘   └───────────┘
```

### Pipeline Nodes

| # | Node | Purpose | API |
|---|------|---------|-----|
| 1 | `interpret_request` | Parse natural language → structured criteria (industry, location, roles) | — |
| 2 | `create_plan` | Generate research steps | — |
| 3 | `discover_companies` | Search for matching companies | Exa + Tavily |
| 4 | `research_companies` | Crawl company websites for details | Firecrawl (mock) |
| 5 | `find_people` | Find CEO/Founder + Marketing Head | Exa + Tavily |
| 6 | `enrich_contacts` | Discover professional email addresses | Hunter |
| 7 | `evaluate_evidence` | Check if 9/9 lead fields are filled | — |
| 8 | `research_missing` | Targeted follow-up for missing fields | Exa + Tavily |
| 9 | `build_lead` | Assemble final Standard Lead JSON | — |

### Intent Understanding

The agent parses 50+ industries, 30+ cities, and 15+ countries from any query:

```
"Find top B2B electronics manufacturers in Bangalore with 100-500 employees"
       ↓
industry: ["Electronics", "B2B"]
location: ["Bangalore", "India"]
employees: 100-500
roles: CEO/Founder, Marketing Head
```

### Output Schema

Each lead contains 15 fields:

```json
{
  "LeadId": "lead_70b99912",
  "Date": "2026-08-18",
  "Category": "Electronics",
  "Segment": null,
  "Industry": "Electronics",
  "Company Name": "NeoDove",
  "Website": "neodove.com",
  "Founded": "2020",
  "Revenue": "$4M",
  "City/Country": "India",
  "Ceo/Founder Name": "Arpit Khandelwal",
  "CEO Linkedn": null,
  "Marketing Head name": "Paras Kapoor",
  "Marketing Head Linkedn": null,
  "Contact email": "contact@neodove.com"
}
```

---

## Project Structure

```
Leads_Scraper/
├── app/
│   ├── __init__.py
│   ├── config.py              # Loads .env, exposes API keys
│   ├── server.py              # Flask + SSE server
│   ├── main.py                # CLI entry point
│   ├── graph.py               # LangGraph workflow definition
│   ├── state.py               # ResearchState TypedDict
│   ├── models.py              # Pydantic models (StandardLead, etc.)
│   ├── intelligence.py        # Intent parsing + query generation
│   ├── nvidia_intelligence.py # NVIDIA Nemotron reasoning layer
│   ├── evidence.py            # Evidence creation utilities
│   ├── lead_builder.py        # Builds leads from collected data
│   ├── nodes/
│   │   ├── interpret_request.py
│   │   ├── create_plan.py
│   │   ├── discover_companies.py
│   │   ├── research_companies.py
│   │   ├── find_people.py
│   │   ├── enrich_contacts.py
│   │   ├── evaluate_evidence.py
│   │   ├── research_missing.py
│   │   └── build_lead.py
│   ├── providers/
│   │   ├── exa.py             # Exa search (real API)
│   │   ├── tavily.py          # Tavily search (real API)
│   │   ├── firecrawl.py       # Firecrawl crawl (mock)
│   │   ├── hunter.py          # Hunter email (real API)
│   │   └── nvidia.py          # NVIDIA Nemotron LLM
│   └── static/
│       └── index.html         # Browser UI with workflow animation
├── output/
│   ├── leads.json             # Final leads
│   └── evidence.json          # Raw evidence
├── .env                       # API keys (git-ignored)
├── .gitignore
└── pyproject.toml
```

---

## Setup

### Prerequisites

- Python 3.11+
- API keys (free tiers work):
  - [Exa](https://exa.ai) — company/people search
  - [Tavily](https://tavily.com) — web search
  - [Hunter](https://hunter.io) — email discovery
  - NVIDIA (optional) — Nemotron reasoning

### Installation

```bash
git clone https://github.com/amritauji/Leads_Scraper.git
cd Leads_Scraper
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux
pip install -e .
```

### Configure API Keys

Create `.env` in the project root:

```env
EXA_API_KEY=your_exa_key
TAVILY_API_KEY=your_tavily_key
HUNTER_API_KEY=your_hunter_key
NVIDIA_API_KEY=your_nvidia_key    # optional
FIRECRAWL_API_KEY=                # optional (mock if empty)
```

### Run

**Web UI (recommended):**
```bash
python -m app.server
# Open http://localhost:5000
```

**CLI:**
```bash
python -m app.main
python -m app.main --use-nvidia    # with Nemotron reasoning
```

---

## API Keys & Free Tier Limits

| Provider | Free Tier | Per-Run Usage | Monthly Budget |
|----------|-----------|---------------|----------------|
| Exa | 1,000 searches | ~10 queries | ~100 runs |
| Tavily | 1,000 searches | ~5 queries | ~200 runs |
| Hunter | 50 searches | 2 calls (capped) | ~25 runs |
| Firecrawl | — | Mock (no key needed) | ∞ |

Hunter is **hard-capped at 2 API calls per pipeline run** to preserve free-tier credits.

---

## Development

### Adding a New Provider

1. Create `app/providers/your_provider.py`
2. Implement the provider class with a `search()` or equivalent method
3. Add it to `app/graph.py` in `build_research_graph()`
4. Wire it into the relevant node(s)

### Adding a New Node

1. Create `app/nodes/your_node.py` with a `create_your_node()` factory
2. Add the node to `app/graph.py`:
   ```python
   graph.add_node("your_node", your_node_func)
   graph.add_edge("previous_node", "your_node")
   ```
3. Update the edge wiring

### Running Tests

```bash
python -m app.main    # verifies full pipeline end-to-end
```

### Code Style

- Python 3.11+ with type hints
- Pydantic for data models
- No comments unless explaining non-obvious logic
- 4-space indentation
- `from __future__ import annotations` in every file

---

## How the UI Works

The browser UI (`app/static/index.html`) connects to the Flask server via:

1. **POST `/api/research`** — starts a background pipeline job
2. **GET `/api/stream/<job_id>`** — SSE stream of progress events

Events flow:
```
node_start → node_start → ... → complete → done
     ↓           ↓                    ↓
  Agent      Exa search          Table/JSON
  (pulsing)  (pulsing)           rendered
```

Each node pulses blue while active, turns green when complete.

---

## License

MIT
