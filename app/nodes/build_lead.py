"""Node: Build Standard Lead

Assembles the final Standard Lead JSON from all collected evidence and entities.
"""

from __future__ import annotations

from typing import Any

from app.intelligence import IntelligenceProvider
from app.lead_builder import build_leads
from app.state import ResearchState


def create_build_lead_node(intelligence: IntelligenceProvider):
    """Create a node that builds the final Standard Lead JSON."""

    def build_lead(state: ResearchState) -> dict[str, Any]:
        criteria = state["criteria"]
        max_companies = state.get("max_companies", 5)
        companies = state.get("companies", [])[:max_companies]
        people = state.get("people", [])
        contacts = state.get("contacts", [])
        evidence = state.get("evidence", [])

        leads = build_leads(
            intelligence=intelligence,
            criteria=criteria,
            companies=companies,
            people=people,
            contacts=contacts,
            evidence=evidence,
        )

        log_entry = f"[build_lead] Built {len(leads)} Standard Lead(s)"
        return {
            "leads": leads,
            "log": state["log"] + [log_entry],
        }

    return build_lead
