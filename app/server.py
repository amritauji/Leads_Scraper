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

    # Phase 2: Data Quality -> Confidence -> Review -> Lead Master
    _push(job_id, {"type": "node_start", "node": "phase2", "display": "Data Quality",
                    "tool": "clean+validate+dedup", "icon": "agent",
                    "message": "Running data quality checks...", "step_index": 8, "total_steps": 10})
    time.sleep(0.3)

    from app.phase2 import Phase2Pipeline
    pipeline = Phase2Pipeline()
    phase2_result = pipeline.process_leads(leads, research_job_id=job_id)

    _push(job_id, {"type": "node_start", "node": "phase2_confidence", "display": "Confidence",
                    "tool": "scoring", "icon": "agent",
                    "message": "Scoring lead confidence...", "step_index": 9, "total_steps": 10})
    time.sleep(0.3)

    # Save to output/
    import os
    os.makedirs("output", exist_ok=True)
    with open("output/leads.json", "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, default=str)
    with open("output/evidence.json", "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, default=str)

    # Collect phase2 stats
    lm_store = pipeline.lead_master
    rq_store = pipeline.review_queue
    phase2_stats = pipeline.get_stats()

    _push(job_id, {
        "type": "complete",
        "leads": leads,
        "companies": companies,
        "people": people,
        "contacts": contacts,
        "evidence_count": len(evidence),
        "log": log,
        "phase2": phase2_stats,
        "lead_master_count": lm_store.count(),
        "review_queue_count": len(rq_store.get_pending()),
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


@app.route("/api/lead-master")
def get_lead_master():
    """Get all Lead Master records."""
    from app.lead_master.store import LeadMasterStore
    store = LeadMasterStore()
    return jsonify({"records": store.to_list(), "count": store.count()})


@app.route("/api/review-queue")
def get_review_queue():
    """Get all pending review items."""
    from app.review.queue import ReviewQueue
    rq = ReviewQueue()
    items = [i.to_dict() for i in rq.get_pending()]
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/review-queue/<review_id>/approve", methods=["POST"])
def approve_review(review_id: str):
    """Approve a review item."""
    from app.phase2 import Phase2Pipeline
    pipeline = Phase2Pipeline()
    result = pipeline.approve_review(review_id)
    if result:
        return jsonify({"status": "approved", "master": result})
    return jsonify({"error": "not found"}), 404


@app.route("/api/quality-results/<quality_result_id>")
def get_quality_result(quality_result_id: str):
    """Get a Data Quality Result by ID."""
    from app.db.quality_store import QualityResultStore
    store = QualityResultStore()
    result = store.get_by_id(quality_result_id)
    if result:
        return jsonify(result.to_dict())
    return jsonify({"error": "not found"}), 404


@app.route("/api/confidence-results/<confidence_result_id>")
def get_confidence_result(confidence_result_id: str):
    """Get a Confidence Result by ID."""
    from app.db.confidence_store import ConfidenceResultStore
    store = ConfidenceResultStore()
    result = store.get_by_id(confidence_result_id)
    if result:
        return jsonify(result.to_dict())
    return jsonify({"error": "not found"}), 404


@app.route("/api/duplicate-events")
def get_duplicate_events():
    """Get all duplicate events."""
    from app.db.duplicate_store import DuplicateEventStore
    store = DuplicateEventStore()
    events = [e.to_dict() for e in store.get_all()]
    return jsonify({"events": events, "count": len(events)})


# ============================================================================
# Phase 3: Users
# ============================================================================

@app.route("/api/users", methods=["GET"])
def list_users():
    from app.users.store import UserStore
    store = UserStore()
    active_only = request.args.get("active_only", "false").lower() == "true"
    users = [u.to_dict() for u in store.get_all(active_only=active_only)]
    return jsonify({"users": users, "count": len(users)})


@app.route("/api/users", methods=["POST"])
def create_user():
    from app.users.store import UserStore
    from app.models import AppUser
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    role = data.get("role", "bd").strip()
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400
    if role not in ("admin", "manager", "bd"):
        return jsonify({"error": "role must be admin, manager, or bd"}), 400
    store = UserStore()
    if store.get_by_email(email):
        return jsonify({"error": "email already exists"}), 409
    user = AppUser(name=name, email=email, role=role)
    user = store.add(user)
    return jsonify(user.to_dict()), 201


@app.route("/api/users/<user_id>", methods=["GET"])
def get_user(user_id: str):
    from app.users.store import UserStore
    store = UserStore()
    user = store.get_by_id(user_id)
    if user:
        return jsonify(user.to_dict())
    return jsonify({"error": "not found"}), 404


@app.route("/api/users/<user_id>", methods=["PATCH"])
def update_user(user_id: str):
    from app.users.store import UserStore
    store = UserStore()
    data = request.get_json(force=True)
    name = data.get("name")
    role = data.get("role")
    is_active = data.get("is_active")
    if role is not None and role not in ("admin", "manager", "bd"):
        return jsonify({"error": "role must be admin, manager, or bd"}), 400
    user = store.update(user_id, name=name, role=role, is_active=is_active)
    if user:
        return jsonify(user.to_dict())
    return jsonify({"error": "not found"}), 404


# ============================================================================
# Phase 3: Lead Master enhanced listing
# ============================================================================

@app.route("/api/lead-master")
def get_lead_master():
    """Get Lead Master records with optional filters."""
    from app.lead_master.store import LeadMasterStore
    store = LeadMasterStore()
    filters = {}
    for key in ("assigned_to", "pipeline_stage", "priority", "status", "confidence_level"):
        val = request.args.get(key)
        if val:
            filters[key] = val
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    records = store.get_all(limit=limit, offset=offset, **filters)
    return jsonify({"records": [r.to_dict() for r in records], "count": store.count()})


# ============================================================================
# Phase 3: Assignment
# ============================================================================

@app.route("/api/lead-master/<master_id>/assign", methods=["POST"])
def assign_lead(master_id: str):
    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True)
    assigned_to = data.get("assigned_to", "").strip()
    assigned_by = data.get("assigned_by", "").strip()
    reason = data.get("reason")
    if not assigned_to or not assigned_by:
        return jsonify({"error": "assigned_to and assigned_by are required"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.assign(master_id, assigned_to, assigned_by, reason)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/reassign", methods=["POST"])
def reassign_lead(master_id: str):
    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True)
    new_user = data.get("assigned_to", "").strip()
    assigned_by = data.get("assigned_by", "").strip()
    reason = data.get("reason")
    if not new_user or not assigned_by:
        return jsonify({"error": "assigned_to and assigned_by are required"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.reassign(master_id, new_user, assigned_by, reason)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/unassign", methods=["POST"])
def unassign_lead(master_id: str):
    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True)
    performed_by = data.get("performed_by", "").strip()
    reason = data.get("reason")
    if not performed_by:
        return jsonify({"error": "performed_by is required"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.unassign(master_id, performed_by, reason)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/assignment-history")
def assignment_history(master_id: str):
    from app.lead_master.service import LeadMasterService
    svc = LeadMasterService()
    history = svc.get_assignment_history(master_id)
    return jsonify({"history": [h.to_dict() for h in history], "count": len(history)})


# ============================================================================
# Phase 3: Pipeline
# ============================================================================

@app.route("/api/lead-master/<master_id>/stage", methods=["POST"])
def change_stage(master_id: str):
    from app.lead_master.service import LeadMasterService
    from app.config import PIPELINE_STAGES
    data = request.get_json(force=True)
    to_stage = data.get("stage", "").strip()
    changed_by = data.get("changed_by", "").strip()
    reason = data.get("reason")
    if not to_stage:
        return jsonify({"error": "stage is required"}), 400
    if to_stage not in PIPELINE_STAGES:
        return jsonify({"error": f"Invalid stage. Valid: {PIPELINE_STAGES}"}), 400
    if not changed_by:
        return jsonify({"error": "changed_by is required"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.change_stage(master_id, to_stage, changed_by, reason)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/pipeline-history")
def pipeline_history(master_id: str):
    from app.lead_master.service import LeadMasterService
    svc = LeadMasterService()
    history = svc.get_pipeline_history(master_id)
    return jsonify({"history": [h.to_dict() for h in history], "count": len(history)})


# ============================================================================
# Phase 3: Priority
# ============================================================================

@app.route("/api/lead-master/<master_id>/priority", methods=["POST"])
def change_priority(master_id: str):
    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True)
    priority = data.get("priority", "").strip()
    performed_by = data.get("performed_by", "").strip()
    if not priority:
        return jsonify({"error": "priority is required"}), 400
    if priority not in ("low", "medium", "high"):
        return jsonify({"error": "priority must be low, medium, or high"}), 400
    if not performed_by:
        return jsonify({"error": "performed_by is required"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.change_priority(master_id, priority, performed_by)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ============================================================================
# Phase 3: Next Action
# ============================================================================

@app.route("/api/lead-master/<master_id>/next-action", methods=["POST"])
def set_next_action(master_id: str):
    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True)
    action_type = data.get("action_type", "").strip()
    action_at = data.get("action_at", "").strip()
    performed_by = data.get("performed_by", "").strip()
    if not action_type or not action_at or not performed_by:
        return jsonify({"error": "action_type, action_at, and performed_by are required"}), 400
    if action_type not in ("call", "email", "meeting", "follow_up", "other"):
        return jsonify({"error": "Invalid action_type"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.set_next_action(master_id, action_type, action_at, performed_by)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/next-action", methods=["DELETE"])
def clear_next_action(master_id: str):
    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True) if request.data else {}
    performed_by = data.get("performed_by", "").strip()
    if not performed_by:
        return jsonify({"error": "performed_by is required"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.clear_next_action(master_id, performed_by)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ============================================================================
# Phase 3: Activities
# ============================================================================

@app.route("/api/lead-master/<master_id>/activities")
def get_activities(master_id: str):
    from app.lead_master.service import LeadMasterService
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    svc = LeadMasterService()
    activities = svc.get_activities(master_id, limit, offset)
    return jsonify({"activities": [a.to_dict() for a in activities], "count": len(activities)})


@app.route("/api/lead-master/<master_id>/activities", methods=["POST"])
def log_activity(master_id: str):
    from app.lead_master.service import LeadMasterService
    from app.config import MANUAL_ACTIVITY_TYPES
    data = request.get_json(force=True)
    activity_type = data.get("activity_type", "").strip()
    performed_by = data.get("performed_by", "").strip()
    title = data.get("title", "").strip()
    description = data.get("description")
    metadata = data.get("metadata", {})
    if not activity_type or not performed_by or not title:
        return jsonify({"error": "activity_type, performed_by, and title are required"}), 400
    if activity_type not in MANUAL_ACTIVITY_TYPES:
        return jsonify({"error": f"Invalid type. Manual types: {MANUAL_ACTIVITY_TYPES}"}), 400
    try:
        svc = LeadMasterService()
        activity = svc.log_manual_activity(master_id, activity_type, performed_by, title, description, metadata)
        return jsonify(activity.to_dict()), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n  Lead Research Agent — http://localhost:5000\n")
    app.run(debug=True, port=5000, threaded=True)
