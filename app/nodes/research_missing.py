"""Node: Research Missing

Generates targeted search queries for missing information and performs additional research.
"""

from __future__ import annotations

from typing import Any

from app.evidence import search_result_to_evidence
from app.intelligence import IntelligenceProvider
from app.providers.exa import ExaProvider
from app.providers.tavily import TavilyProvider
from app.state import ResearchState


def create_research_missing_node(
    intelligence: IntelligenceProvider,
    exa: ExaProvider,
    tavily: TavilyProvider,
):
    """Create a node that researches missing information with targeted queries."""

    def research_missing(state: ResearchState) -> dict[str, Any]:
        criteria = state["criteria"]
        companies = state.get("companies", [])
        people = state.get("people", [])
        missing = state.get("missing_information", [])
        evidence: list[dict[str, Any]] = list(state.get("evidence", []))
        iteration = state.get("iteration", 0)

        # Generate targeted queries for missing information
        queries = intelligence.generate_search_queries(
            criteria=criteria,
            plan=state.get("research_plan", []),
            missing=missing,
            known_companies=companies,
            known_people=people,
        )

        companies_updated = list(companies)
        people_updated = list(people)

        for query in queries:
            # Search with Exa
            exa_results = exa.search(query, num_results=3)
            for result in exa_results:
                ev = search_result_to_evidence(result)
                evidence.append(ev.to_dict())
                _merge_findings(result, companies_updated, people_updated, ev.id)

            # Search with Tavily
            tavily_results = tavily.search(query, num_results=2)
            for result in tavily_results:
                ev = search_result_to_evidence(result)
                evidence.append(ev.to_dict())
                _merge_findings(result, companies_updated, people_updated, ev.id)

        log_entry = f"[research_missing] Iteration {iteration + 1}: Generated {len(queries)} targeted queries, evidence total: {len(evidence)}"
        return {
            "companies": companies_updated,
            "people": people_updated,
            "evidence": evidence,
            "iteration": iteration + 1,
            "search_queries": queries,
            "log": state["log"] + [log_entry],
        }

    return research_missing


def _merge_findings(result, companies: list[dict], people: list[dict], evidence_id: str):
    """Merge findings from search results into existing company/person records."""
    import re

    content = (result.content or "").lower()
    title = result.title or ""

    # Try to fill in missing employee counts
    for company in companies:
        if not company.get("employee_count"):
            emp_match = re.search(r"(\d[\d,]*)\s*(?:\+?\s*)?(?:employee|staff|member|people)", content)
            if emp_match and company.get("name", "").lower() in content:
                company["employee_count"] = int(emp_match.group(1).replace(",", ""))
                company.setdefault("evidence_ids", []).append(evidence_id)

    # Try to find additional people
    for company in companies:
        company_name = company.get("name", "")
        if not company_name or company_name.lower() not in content:
            continue

        name_match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)+),?\s*(?:CFO|CTO|CEO|VP|Head|Director|Chief)", title)
        if name_match:
            person_name = name_match.group(1)
            if not any(p.get("name", "").lower() == person_name.lower() for p in people):
                people.append({
                    "name": person_name,
                    "title": "Decision Maker",
                    "company_name": company_name,
                    "linkedin_url": None,
                    "evidence_ids": [evidence_id],
                })
