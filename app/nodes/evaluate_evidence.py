"""Node: Evaluate Evidence

Assesses what information has been gathered and identifies missing fields.
"""

from __future__ import annotations

from typing import Any

from app.intelligence import IntelligenceProvider
from app.state import ResearchState


def create_evaluate_evidence_node(intelligence: IntelligenceProvider):
    """Create a node that evaluates evidence completeness."""

    def evaluate_evidence(state: ResearchState) -> dict[str, Any]:
        criteria = state["criteria"]
        companies = state.get("companies", [])
        people = state.get("people", [])
        contacts = state.get("contacts", [])
        evidence = state.get("evidence", [])
        iteration = state.get("iteration", 0)

        missing = intelligence.evaluate_evidence(
            criteria, companies, people, contacts, evidence
        )

        # Build completeness summary for required lead fields
        ceo_founders = [p for p in people if p.get("role") == "ceo_founder"]
        marketing_heads = [p for p in people if p.get("role") == "marketing_head"]

        status = {
            "company_name": bool(any(c.get("name") for c in companies)),
            "industry": bool(any(c.get("industry") for c in companies)),
            "website": bool(any(c.get("website") for c in companies)),
            "founded": bool(any(c.get("founded") for c in companies)),
            "revenue": bool(any(c.get("revenue") for c in companies)),
            "city_country": bool(any(c.get("location") or c.get("city") for c in companies)),
            "ceo_founder": bool(ceo_founders),
            "marketing_head": bool(marketing_heads),
            "contact_email": bool(any(c.get("email") for c in contacts)),
        }

        found_count = sum(1 for v in status.values() if v)
        total_count = len(status)

        log_entry = f"[evaluate_evidence] Iteration {iteration + 1}: {found_count}/{total_count} fields filled. Missing: {missing if missing else 'none'}"
        return {
            "missing_information": missing,
            "log": state["log"] + [log_entry],
        }

    return evaluate_evidence
