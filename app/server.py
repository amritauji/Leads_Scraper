"""Flask server for the Lead Research Agent visualization.

Run:
    python -m app.server
    # Then open http://localhost:5000
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from typing import Any

from flask import Flask, Response, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------
_jobs: dict[str, queue.Queue] = {}


def _push(job_id: str, event: dict):
    q = _jobs.get(job_id)
    if q:
        q.put(event)


# ---------------------------------------------------------------------------
# Pipeline wrapper that emits SSE events
# ---------------------------------------------------------------------------
def _run_pipeline(job_id: str, query: str, max_companies: int = 5):
    """Run the research graph, posting progress events to the job queue."""
    from app.graph import build_research_graph
    from app.intelligence import MockIntelligenceProvider
    from app.providers.exa import ExaProvider
    from app.providers.tavily import TavilyProvider
    from app.providers.firecrawl import FirecrawlProvider
    from app.providers.hunter import HunterProvider
    from app.state import create_initial_state

    intelligence = MockIntelligenceProvider()
    exa = ExaProvider()
    tavily = TavilyProvider()
    firecrawl = FirecrawlProvider()
    hunter = HunterProvider()

    graph = build_research_graph(
        intelligence=intelligence, exa=exa, tavily=tavily,
        firecrawl=firecrawl, hunter=hunter,
    )

    # Map graph node names → display names & tool info
    node_map = {
        "interpret_request":  {"display": "Agent",        "tool": "intent",     "icon": "agent"},
        "create_research_plan": {"display": "Agent",      "tool": "planning",   "icon": "agent"},
        "discover_companies":  {"display": "Exa",         "tool": "search",     "icon": "exa"},
        "research_companies":  {"display": "Firecrawl",   "tool": "crawl",      "icon": "firecrawl"},
        "find_people":         {"display": "Exa + Tavily","tool": "people",     "icon": "tools"},
        "enrich_contacts":     {"display": "Hunter",      "tool": "email",      "icon": "hunter"},
        "evaluate_evidence":   {"display": "Agent",       "tool": "evaluate",   "icon": "agent"},
        "research_missing":    {"display": "Tools",       "tool": "follow-up",  "icon": "tools"},
        "build_standard_lead": {"display": "Agent",       "tool": "assemble",   "icon": "agent"},
    }

    state = create_initial_state(query, max_iterations=1)
    state["max_companies"] = max_companies

    # We monkey-patch the compiled graph's stream to intercept node execution
    # Instead, we just run invoke and emit synthetic progress events
    _push(job_id, {"type": "start", "query": query, "max_companies": max_companies})

    steps = [
        ("interpret_request",  "Agent interpreting your request..."),
        ("create_research_plan", "Agent creating research plan..."),
        ("discover_companies",  "Exa searching for companies..."),
        ("research_companies",  "Firecrawl crawling company websites..."),
        ("find_people",         "Exa + Tavily finding people..."),
        ("enrich_contacts",     "Hunter discovering emails..."),
        ("evaluate_evidence",   "Agent evaluating evidence quality..."),
        ("build_standard_lead", "Agent assembling final leads..."),
    ]

    def _emit_step(idx: int, node_name: str, msg: str):
        info = node_map.get(node_name, {"display": node_name, "tool": "", "icon": "agent"})
        _push(job_id, {
            "type": "node_start",
            "node": node_name,
            "display": info["display"],
            "tool": info["tool"],
            "icon": info["icon"],
            "message": msg,
            "step_index": idx,
            "total_steps": len(steps),
        })

    # Emit steps with slight delays so the UI can animate
    # (real work happens inside graph.invoke below — we pre-emit for animation)
    for idx, (node_name, msg) in enumerate(steps):
        _emit_step(idx, node_name, msg)
        time.sleep(0.3)

    # Actually run the graph
    _push(job_id, {"type": "graph_start"})
    try:
        final_state = graph.invoke(state)
    except Exception as e:
        _push(job_id, {"type": "error", "message": str(e)})
        return

    # Build results
    leads = final_state.get("leads", [])[:max_companies]
    evidence = final_state.get("evidence", [])
    companies = final_state.get("companies", [])[:max_companies]
    people = final_state.get("people", [])
    contacts = final_state.get("contacts", [])
    log = final_state.get("log", [])

    # Save to output/
    import os
    os.makedirs("output", exist_ok=True)
    with open("output/leads.json", "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, default=str)
    with open("output/evidence.json", "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, default=str)

    _push(job_id, {
        "type": "complete",
        "leads": leads,
        "companies": companies,
        "people": people,
        "contacts": contacts,
        "evidence_count": len(evidence),
        "log": log,
    })

    # Mark done
    _push(job_id, {"type": "done"})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/research", methods=["POST"])
def start_research():
    """Start a research job. Returns job_id for SSE subscription."""
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    max_companies = int(data.get("max_companies", 5))

    if not query:
        return jsonify({"error": "query is required"}), 400

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = queue.Queue()

    thread = threading.Thread(target=_run_pipeline, args=(job_id, query, max_companies), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/stream/<job_id>")
def stream(job_id: str):
    """SSE endpoint that streams progress for a job."""
    q = _jobs.get(job_id)
    if not q:
        return jsonify({"error": "job not found"}), 404

    def generate():
        while True:
            try:
                event = q.get(timeout=60)
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                continue

            yield f"data: {json.dumps(event, default=str)}\n\n"

            if event.get("type") in ("done", "error"):
                break

    return Response(generate(), mimetype="text/event-stream")


@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory("output", filename)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n  Lead Research Agent — http://localhost:5000\n")
    app.run(debug=True, port=5000, threaded=True)
