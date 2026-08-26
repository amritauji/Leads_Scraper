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

from app.auth.dependencies import get_current_user
from app.auth.current_user import CurrentUser
from app.auth.permissions import (
    require_can_assign,
    require_can_manage_leads,
    require_can_manage_users,
    require_can_review,
    require_lead_access,
    require_authenticated,
)
from app.auth.jwt import AuthError

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
# Auth helper: extract current user or return error response
# ---------------------------------------------------------------------------
def _get_user_or_error() -> tuple[CurrentUser | None, tuple]:
    """Get current user from JWT, or (None, error_response)."""
    user = get_current_user()
    try:
        user = require_authenticated(user)
    except AuthError as e:
        return None, (jsonify({"error": e.message}), e.status)
    return user, None


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

    for idx, (node_name, msg) in enumerate(steps):
        _emit_step(idx, node_name, msg)
        time.sleep(0.3)

    _push(job_id, {"type": "graph_start"})
    try:
        final_state = graph.invoke(state)
    except Exception as e:
        _push(job_id, {"type": "error", "message": str(e)})
        return

    leads = final_state.get("leads", [])[:max_companies]
    evidence = final_state.get("evidence", [])
    companies = final_state.get("companies", [])[:max_companies]
    people = final_state.get("people", [])
    contacts = final_state.get("contacts", [])
    log = final_state.get("log", [])

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

    import os
    os.makedirs("output", exist_ok=True)
    with open("output/leads.json", "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, default=str)
    with open("output/evidence.json", "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, default=str)

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

    _push(job_id, {"type": "done"})


# ---------------------------------------------------------------------------
# Public routes (no auth required)
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


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
# Protected routes: Research
# ---------------------------------------------------------------------------
@app.route("/api/research", methods=["POST"])
def start_research():
    """Start a research job. Returns job_id for SSE subscription."""
    user, err = _get_user_or_error()
    if err:
        return err

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


# ---------------------------------------------------------------------------
# Protected routes: Lead Master (Phase 1-2 data)
# ---------------------------------------------------------------------------
@app.route("/api/lead-master")
def get_lead_master():
    """Get Lead Master records with optional filters.

    BD users see only their assigned leads.
    Admin/Manager see all leads.
    """
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.store import LeadMasterStore
    store = LeadMasterStore()

    filters = {}
    for key in ("assigned_to", "pipeline_stage", "priority", "status", "confidence_level"):
        val = request.args.get(key)
        if val:
            filters[key] = val
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    # BD users: enforce ownership filter
    if user.is_bd:
        filters["assigned_to"] = user.user_id

    records = store.get_all(limit=limit, offset=offset, **filters)
    return jsonify({"records": [r.to_dict() for r in records], "count": store.count()})


@app.route("/api/lead-master/<master_id>")
def get_lead_by_id(master_id: str):
    """Get a single Lead Master record."""
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.store import LeadMasterStore
    store = LeadMasterStore()
    record = store.get_by_id(master_id)
    if not record:
        return jsonify({"error": "not found"}), 404

    require_lead_access(user, record.assigned_to)
    return jsonify(record.to_dict())


# ---------------------------------------------------------------------------
# Protected routes: Review Queue (admin/manager only)
# ---------------------------------------------------------------------------
@app.route("/api/review-queue")
def get_review_queue():
    """Get all pending review items. Admin/Manager only."""
    user, err = _get_user_or_error()
    if err:
        return err
    require_can_review(user)

    from app.review.queue import ReviewQueue
    rq = ReviewQueue()
    items = [i.to_dict() for i in rq.get_pending()]
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/review-queue/<review_id>/approve", methods=["POST"])
def approve_review(review_id: str):
    """Approve a review item. Admin/Manager only."""
    user, err = _get_user_or_error()
    if err:
        return err
    require_can_review(user)

    from app.phase2 import Phase2Pipeline
    pipeline = Phase2Pipeline()
    result = pipeline.approve_review(review_id, reviewed_by=user.user_id)
    if result:
        return jsonify({"status": "approved", "master": result})
    return jsonify({"error": "not found"}), 404


# ---------------------------------------------------------------------------
# Protected routes: Quality & Confidence (auth required)
# ---------------------------------------------------------------------------
@app.route("/api/quality-results/<quality_result_id>")
def get_quality_result(quality_result_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.db.quality_store import QualityResultStore
    store = QualityResultStore()
    result = store.get_by_id(quality_result_id)
    if result:
        return jsonify(result.to_dict())
    return jsonify({"error": "not found"}), 404


@app.route("/api/confidence-results/<confidence_result_id>")
def get_confidence_result(confidence_result_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.db.confidence_store import ConfidenceResultStore
    store = ConfidenceResultStore()
    result = store.get_by_id(confidence_result_id)
    if result:
        return jsonify(result.to_dict())
    return jsonify({"error": "not found"}), 404


@app.route("/api/duplicate-events")
def get_duplicate_events():
    user, err = _get_user_or_error()
    if err:
        return err

    from app.db.duplicate_store import DuplicateEventStore
    store = DuplicateEventStore()
    events = [e.to_dict() for e in store.get_all()]
    return jsonify({"events": events, "count": len(events)})


# ============================================================================
# Protected routes: Users (admin only for create/update, any auth for list/get)
# ============================================================================

@app.route("/api/users", methods=["GET"])
def list_users():
    user, err = _get_user_or_error()
    if err:
        return err

    from app.users.store import UserStore
    store = UserStore()
    active_only = request.args.get("active_only", "false").lower() == "true"
    users = [u.to_dict() for u in store.get_all(active_only=active_only)]
    return jsonify({"users": users, "count": len(users)})


@app.route("/api/users", methods=["POST"])
def create_user():
    """Create a user. Admin only."""
    user, err = _get_user_or_error()
    if err:
        return err
    require_can_manage_users(user)

    from app.users.store import UserStore
    from app.models import AppUser
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    role = data.get("role", "bd").strip()
    auth_user_id = data.get("auth_user_id", "").strip() or None
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400
    if role not in ("admin", "manager", "bd"):
        return jsonify({"error": "role must be admin, manager, or bd"}), 400
    store = UserStore()
    if store.get_by_email(email):
        return jsonify({"error": "email already exists"}), 409
    new_user = AppUser(name=name, email=email, role=role, auth_user_id=auth_user_id)
    new_user = store.add(new_user)
    return jsonify(new_user.to_dict()), 201


@app.route("/api/users/<user_id>", methods=["GET"])
def get_user(user_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.users.store import UserStore
    store = UserStore()
    target = store.get_by_id(user_id)
    if target:
        return jsonify(target.to_dict())
    return jsonify({"error": "not found"}), 404


@app.route("/api/users/<user_id>", methods=["PATCH"])
def update_user(user_id: str):
    """Update a user. Admin only."""
    user, err = _get_user_or_error()
    if err:
        return err
    require_can_manage_users(user)

    from app.users.store import UserStore
    store = UserStore()
    data = request.get_json(force=True)
    name = data.get("name")
    role = data.get("role")
    is_active = data.get("is_active")
    auth_user_id = data.get("auth_user_id")
    if role is not None and role not in ("admin", "manager", "bd"):
        return jsonify({"error": "role must be admin, manager, or bd"}), 400
    target = store.update(user_id, name=name, role=role, is_active=is_active, auth_user_id=auth_user_id)
    if target:
        return jsonify(target.to_dict())
    return jsonify({"error": "not found"}), 404


# ============================================================================
# Protected routes: Assignment (admin/manager only for assign/reassign/unassign)
# ============================================================================

@app.route("/api/lead-master/<master_id>/assign", methods=["POST"])
def assign_lead(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err
    require_can_assign(user)

    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True)
    assigned_to = data.get("assigned_to", "").strip()
    reason = data.get("reason")
    if not assigned_to:
        return jsonify({"error": "assigned_to is required"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.assign(master_id, assigned_to, user.user_id, reason)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/reassign", methods=["POST"])
def reassign_lead(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err
    require_can_assign(user)

    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True)
    new_user = data.get("assigned_to", "").strip()
    reason = data.get("reason")
    if not new_user:
        return jsonify({"error": "assigned_to is required"}), 400
    try:
        svc = LeadMasterService()
        lead = svc.reassign(master_id, new_user, user.user_id, reason)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/unassign", methods=["POST"])
def unassign_lead(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err
    require_can_assign(user)

    from app.lead_master.service import LeadMasterService
    data = request.get_json(force=True) if request.data else {}
    reason = data.get("reason")
    try:
        svc = LeadMasterService()
        lead = svc.unassign(master_id, user.user_id, reason)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/assignment-history")
def assignment_history(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.service import LeadMasterService
    svc = LeadMasterService()
    history = svc.get_assignment_history(master_id)
    return jsonify({"history": [h.to_dict() for h in history], "count": len(history)})


# ============================================================================
# Protected routes: Pipeline (admin/manager for stage changes; BD can change on own leads)
# ============================================================================

@app.route("/api/lead-master/<master_id>/stage", methods=["POST"])
def change_stage(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.service import LeadMasterService
    from app.lead_master.store import LeadMasterStore
    from app.config import PIPELINE_STAGES

    store = LeadMasterStore()
    record = store.get_by_id(master_id)
    if not record:
        return jsonify({"error": "not found"}), 404

    # BD users can only change stage on their own leads
    require_lead_access(user, record.assigned_to)

    data = request.get_json(force=True)
    to_stage = data.get("stage", "").strip()
    reason = data.get("reason")
    if not to_stage:
        return jsonify({"error": "stage is required"}), 400
    if to_stage not in PIPELINE_STAGES:
        return jsonify({"error": f"Invalid stage. Valid: {PIPELINE_STAGES}"}), 400

    try:
        svc = LeadMasterService()
        lead = svc.change_stage(master_id, to_stage, user.user_id, reason)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/pipeline-history")
def pipeline_history(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.service import LeadMasterService
    svc = LeadMasterService()
    history = svc.get_pipeline_history(master_id)
    return jsonify({"history": [h.to_dict() for h in history], "count": len(history)})


# ============================================================================
# Protected routes: Priority (BD on own leads; admin/manager on any)
# ============================================================================

@app.route("/api/lead-master/<master_id>/priority", methods=["POST"])
def change_priority(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.service import LeadMasterService
    from app.lead_master.store import LeadMasterStore

    store = LeadMasterStore()
    record = store.get_by_id(master_id)
    if not record:
        return jsonify({"error": "not found"}), 404

    require_lead_access(user, record.assigned_to)

    data = request.get_json(force=True)
    priority = data.get("priority", "").strip()
    if not priority:
        return jsonify({"error": "priority is required"}), 400
    if priority not in ("low", "medium", "high"):
        return jsonify({"error": "priority must be low, medium, or high"}), 400

    try:
        svc = LeadMasterService()
        lead = svc.change_priority(master_id, priority, user.user_id)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ============================================================================
# Protected routes: Next Action (BD on own leads; admin/manager on any)
# ============================================================================

@app.route("/api/lead-master/<master_id>/next-action", methods=["POST"])
def set_next_action(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.service import LeadMasterService
    from app.lead_master.store import LeadMasterStore

    store = LeadMasterStore()
    record = store.get_by_id(master_id)
    if not record:
        return jsonify({"error": "not found"}), 404

    require_lead_access(user, record.assigned_to)

    data = request.get_json(force=True)
    action_type = data.get("action_type", "").strip()
    action_at = data.get("action_at", "").strip()
    if not action_type or not action_at:
        return jsonify({"error": "action_type and action_at are required"}), 400
    if action_type not in ("call", "email", "meeting", "follow_up", "other"):
        return jsonify({"error": "Invalid action_type"}), 400

    try:
        svc = LeadMasterService()
        lead = svc.set_next_action(master_id, action_type, action_at, user.user_id)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/lead-master/<master_id>/next-action", methods=["DELETE"])
def clear_next_action(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.service import LeadMasterService
    from app.lead_master.store import LeadMasterStore

    store = LeadMasterStore()
    record = store.get_by_id(master_id)
    if not record:
        return jsonify({"error": "not found"}), 404

    require_lead_access(user, record.assigned_to)

    try:
        svc = LeadMasterService()
        lead = svc.clear_next_action(master_id, user.user_id)
        return jsonify(lead.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ============================================================================
# Protected routes: Activities (BD on own leads; admin/manager on any)
# ============================================================================

@app.route("/api/lead-master/<master_id>/activities")
def get_activities(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.service import LeadMasterService
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    svc = LeadMasterService()
    activities = svc.get_activities(master_id, limit, offset)
    return jsonify({"activities": [a.to_dict() for a in activities], "count": len(activities)})


@app.route("/api/lead-master/<master_id>/activities", methods=["POST"])
def log_activity(master_id: str):
    user, err = _get_user_or_error()
    if err:
        return err

    from app.lead_master.service import LeadMasterService
    from app.lead_master.store import LeadMasterStore
    from app.config import MANUAL_ACTIVITY_TYPES

    store = LeadMasterStore()
    record = store.get_by_id(master_id)
    if not record:
        return jsonify({"error": "not found"}), 404

    require_lead_access(user, record.assigned_to)

    data = request.get_json(force=True)
    activity_type = data.get("activity_type", "").strip()
    title = data.get("title", "").strip()
    description = data.get("description")
    metadata = data.get("metadata", {})
    if not activity_type or not title:
        return jsonify({"error": "activity_type and title are required"}), 400
    if activity_type not in MANUAL_ACTIVITY_TYPES:
        return jsonify({"error": f"Invalid type. Manual types: {MANUAL_ACTIVITY_TYPES}"}), 400

    try:
        svc = LeadMasterService()
        activity = svc.log_manual_activity(master_id, activity_type, user.user_id, title, description, metadata)
        return jsonify(activity.to_dict()), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n  Lead Research Agent — http://localhost:5000\n")
    app.run(debug=True, port=5000, threaded=True)
