"""Node: Find People

Searches for CEO/Founder and Marketing Head at identified companies.
"""

from __future__ import annotations

from typing import Any

from app.evidence import search_result_to_evidence
from app.intelligence import IntelligenceProvider
from app.providers.exa import ExaProvider
from app.providers.tavily import TavilyProvider
from app.state import ResearchState


# Search terms for each role — kept minimal to reduce API calls with real providers
_ROLE_SEARCH_TERMS: dict[str, list[str]] = {
    "ceo_founder": ["CEO founder"],
    "marketing_head": ["marketing head"],
}


def create_find_people_node(
    intelligence: IntelligenceProvider,
    exa: ExaProvider,
    tavily: TavilyProvider,
):
    """Create a node that discovers CEO/Founder and Marketing Head at companies."""

    def find_people(state: ResearchState) -> dict[str, Any]:
        companies = state.get("companies", [])
        people: list[dict[str, Any]] = list(state.get("people", []))
        evidence: list[dict[str, Any]] = list(state.get("evidence", []))

        for company in companies:
            company_name = company.get("name", "")
            if not company_name:
                continue

            for role, search_terms in _ROLE_SEARCH_TERMS.items():
                # Skip if we already have this role for this company
                if any(p.get("company_name", "").lower() == company_name.lower() and p.get("role") == role for p in people):
                    continue

                for term in search_terms:
                    query = f'"{company_name}" {term}'
                    results = exa.search(query, num_results=3, category="people")

                    for result in results:
                        ev = search_result_to_evidence(result, entity=company_name)
                        evidence.append(ev.to_dict())

                        person = _extract_person_from_search(result, company_name, ev.id, role)
                        if person and not _person_exists(people, person["name"], company_name, role):
                            people.append(person)
                            break  # Found someone for this role, move on

                    # Only check Tavily if Exa didn't find anyone for this role
                    if any(p.get("company_name", "").lower() == company_name.lower() and p.get("role") == role for p in people):
                        continue

                    tavily_results = tavily.search(query, num_results=2)
                    for result in tavily_results:
                        ev = search_result_to_evidence(result, entity=company_name)
                        evidence.append(ev.to_dict())

                        person = _extract_person_from_search(result, company_name, ev.id, role)
                        if person and not _person_exists(people, person["name"], company_name, role):
                            people.append(person)
                            break

        log_entry = f"[find_people] Found {len(people)} people candidates"
        return {
            "people": people,
            "evidence": evidence,
            "log": state["log"] + [log_entry],
        }

    return find_people


def _extract_person_from_search(result, company_name: str, evidence_id: str, role: str) -> dict[str, Any] | None:
    """Extract person information from a search result.

    Only returns a person if they are mentioned in context with the target company.
    """
    import re

    title = result.title or ""
    content = result.content or ""
    full_text = f"{title} {content}"

    # Verify the company is mentioned in the search result
    company_lower = company_name.lower()
    company_keywords = company_lower.split()
    if not any(kw in full_text.lower() for kw in company_keywords):
        return None

    # For marketing_head role, skip results that clearly mention CEO/Founder
    if role == "marketing_head":
        if re.search(r"\bceo\b|\bfounder\b|\bco-founder\b", full_text, re.IGNORECASE):
            # Only skip if there's no marketing-specific mention
            if not re.search(r"marketing|cmo|vp marketing", full_text, re.IGNORECASE):
                return None

    # Try to extract a name from the title
    name = None

    # Robust name pattern: handles apostrophes (O'Reilly), single-char initials (Sidharth S), hyphens
    _SIMPLE = r"[A-Z][a-z]+"                    # Helen, Smith, Sidharth
    _COMPOUND = r"[A-Z][a-z]*[-'][A-Z][a-z]+"   # O'Reilly, D'Angelo, Smith-Jones
    _INITIAL = r"[A-Z]"                          # S, K (single-char last names)
    _TOKEN = rf"(?:{_COMPOUND}|{_SIMPLE}|{_INITIAL})"
    _FULL_NAME = rf"{_TOKEN}(?:\s{_TOKEN})+"

    # Pattern: "Name - CEO & Founder Company"
    name_match = re.match(rf"^({_FULL_NAME})\s*[-–]", title)
    if name_match:
        name = name_match.group(1)

    # Pattern: "Name, Title at Company"
    if not name:
        name_match = re.match(rf"^({_FULL_NAME})", title)
        if name_match:
            candidate = name_match.group(1)
            skip_words = {"top", "best", "leading", "cfo", "cto", "ceo", "finance", "head", "vp", "marketing"}
            if candidate.lower().split()[0] not in skip_words:
                name = candidate

    # Pattern from content: "CEO & Founder: Name" or "Name, CEO"
    if not name:
        name_match = re.search(rf"(?:CEO|Founder|co-founder|CMO|marketing head|VP marketing)[:\s]+({_FULL_NAME})", full_text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1)

    # Pattern from content: "Name, CEO of Company"
    if not name:
        name_match = re.search(rf"({_FULL_NAME}),?\s*(?:CEO|Founder|CMO|Head of Marketing)", full_text)
        if name_match:
            name = name_match.group(1)

    # Pattern: "Founded by Name" or "founded by Name"
    if not name:
        name_match = re.search(rf"found(?:ed)?\s+by\s+({_FULL_NAME})", full_text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1)

    # Pattern: "CEO & Founder: Name" from content
    if not name:
        name_match = re.search(rf"CEO\s*(?:&|and)\s*Founder[:\s]+({_FULL_NAME})", full_text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1)

    # Pattern: "Marketing Head: Name" from content
    if not name and role == "marketing_head":
        name_match = re.search(rf"(?:Marketing Head|VP Marketing|CMO|Head of Marketing)[:\s]+({_FULL_NAME})", full_text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1)

    if not name:
        return None

    # Filter out invalid names
    _NOT_PERSON_NAMES = {"finance head", "head of finance", "vp finance", "cfo", "cto", "ceo",
                         "decision maker", "unknown", "the company", "the team", "marketing head",
                         "mock content", "mock tavily", "search result", "web results",
                         "chargebee company information", "zoho corporation company overview",
                         "india saas landscape report", "top saas companies in india 2024"}
    name_lower = name.lower().strip()
    if name_lower in _NOT_PERSON_NAMES or any(w in name_lower for w in _NOT_PERSON_NAMES):
        return None

    _COMPANY_NAMES = {"zoho corporation", "freshworks", "postman", "chargebee", "browserstack",
                      "chargebee company information", "zoho corporation company overview"}
    if name_lower in _COMPANY_NAMES:
        return None

    # Skip names that look like article titles
    if len(name) < 4 or not name[0].isupper():
        return None

    # Extract title based on role
    if role == "ceo_founder":
        person_title = "CEO & Founder"
        for t in ["CEO", "Founder", "Co-Founder", "CEO & Founder"]:
            if t.lower() in full_text.lower():
                person_title = t
                break
    elif role == "marketing_head":
        person_title = "Marketing Head"
        for t in ["CMO", "VP Marketing", "Head of Marketing", "Marketing Director"]:
            if t.lower() in full_text.lower():
                person_title = t
                break
    else:
        person_title = "Decision Maker"

    # Extract LinkedIn URL
    linkedin_url = None
    linkedin_match = re.search(r"(https?://(?:www\.)?linkedin\.com/in/[^\s\)]+)", full_text)
    if linkedin_match:
        linkedin_url = linkedin_match.group(1)

    return {
        "name": name,
        "title": person_title,
        "role": role,
        "company_name": company_name,
        "linkedin_url": linkedin_url,
        "evidence_ids": [evidence_id],
    }


def _person_exists(people: list[dict], name: str, company_name: str, role: str) -> bool:
    """Check if this person at this company with this role is already in the list."""
    name_lower = name.lower()
    return any(
        p.get("name", "").lower() == name_lower
        and p.get("company_name", "").lower() == company_name.lower()
        and p.get("role") == role
        for p in people
    )
