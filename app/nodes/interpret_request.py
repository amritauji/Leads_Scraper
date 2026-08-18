"""Node: Interpret Request

Converts a natural language research request into structured criteria.
"""

from __future__ import annotations

from typing import Any

from app.intelligence import IntelligenceProvider
from app.state import ResearchState


def create_interpret_request_node(intelligence: IntelligenceProvider):
    """Create a node function that interprets the research request."""

    def interpret_request(state: ResearchState) -> dict[str, Any]:
        criteria = intelligence.interpret_request(state["research_request"])
        log_entry = f"[interpret_request] Parsed criteria: industries={criteria.get('company', {}).get('industry', [])}, location={criteria.get('company', {}).get('location', [])}, titles={criteria.get('person', {}).get('target_titles', [])}"
        return {
            "criteria": criteria,
            "log": state["log"] + [log_entry],
        }

    return interpret_request
