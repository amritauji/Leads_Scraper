"""Research state shared across all LangGraph nodes."""

from __future__ import annotations

from typing import Any, TypedDict

from app.models import CompanyCandidate, ContactCandidate, Evidence, PersonCandidate, ResearchCriteria, ResearchPlanStep, StandardLead


class ResearchState(TypedDict):
    """Shared mutable state for the research graph."""

    research_request: str

    criteria: dict[str, Any]

    research_plan: list[dict[str, str]]

    search_queries: list[str]

    companies: list[dict[str, Any]]
    people: list[dict[str, Any]]
    contacts: list[dict[str, Any]]

    evidence: list[dict[str, Any]]

    missing_information: list[str]

    iteration: int
    max_iterations: int
    max_companies: int

    leads: list[dict[str, Any]]

    log: list[str]


def create_initial_state(research_request: str, max_iterations: int = 3, max_companies: int = 5) -> ResearchState:
    """Create a fresh ResearchState for a new research job."""
    return ResearchState(
        research_request=research_request.strip(),
        criteria={},
        research_plan=[],
        search_queries=[],
        companies=[],
        people=[],
        contacts=[],
        evidence=[],
        missing_information=[],
        iteration=0,
        max_iterations=max_iterations,
        max_companies=max_companies,
        leads=[],
        log=[],
    )
