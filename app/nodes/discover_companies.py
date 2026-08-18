"""Node: Discover Companies

Searches for companies matching the research criteria using Exa and Tavily.
"""

from __future__ import annotations

from typing import Any

from app.evidence import search_result_to_evidence
from app.intelligence import IntelligenceProvider
from app.providers.exa import ExaProvider
from app.providers.tavily import TavilyProvider
from app.state import ResearchState


def create_discover_companies_node(
    intelligence: IntelligenceProvider,
    exa: ExaProvider,
    tavily: TavilyProvider,
):
    """Create a node that discovers candidate companies."""

    def discover_companies(state: ResearchState) -> dict[str, Any]:
        criteria = state["criteria"]
        queries = state.get("search_queries", [])
        max_companies = state.get("max_companies", 5)

        # Generate initial queries if none exist yet
        if not queries:
            queries = intelligence.generate_search_queries(
                criteria=criteria,
                plan=state.get("research_plan", []),
                missing=[],
                known_companies=[],
                known_people=[],
            )

        companies: list[dict[str, Any]] = list(state.get("companies", []))
        evidence: list[dict[str, Any]] = list(state.get("evidence", []))
        new_evidence_ids: list[str] = []

        # Use Exa for company discovery — stop when we hit the limit
        for query in queries:
            if len(companies) >= max_companies:
                break
            exa_results = exa.search(query, num_results=5, category="company")
            for result in exa_results:
                if len(companies) >= max_companies:
                    break
                ev = search_result_to_evidence(result, entity=result.title)
                ev_dict = ev.to_dict()
                evidence.append(ev_dict)
                new_evidence_ids.append(ev.id)

                # Extract company info from the search result
                if result.title and result.content:
                    company = _extract_company_from_search(result, ev.id)
                    if company and not _company_exists(companies, company["name"]):
                        companies.append(company)

        # Use Tavily for broader discovery
        for query in queries:
            if len(companies) >= max_companies:
                break
            tavily_results = tavily.search(query, num_results=3)
            for result in tavily_results:
                if len(companies) >= max_companies:
                    break
                ev = search_result_to_evidence(result, entity=result.title)
                ev_dict = ev.to_dict()
                evidence.append(ev_dict)
                new_evidence_ids.append(ev.id)

                if result.title and result.content:
                    company = _extract_company_from_search(result, ev.id)
                    if company and not _company_exists(companies, company["name"]):
                        companies.append(company)

        log_entry = f"[discover_companies] Found {len(companies)} company candidates"
        return {
            "companies": companies,
            "evidence": evidence,
            "log": state["log"] + [log_entry],
        }

    return discover_companies


# Patterns that indicate this is NOT a company entry
_NON_COMPANY_PATTERNS = [
    r"^(?:CFO|CTO|CEO|VP|Head|Director|Chief)\s+at\s+",
    r"^(?:Top|Best|Leading)\s+",
    r"(?:Report|Landscape|Guide|Review|List|Directory|Analysis)$",
    r"^(?:What|How|Why|When|Where)\s+",
    r"^\d{4}\s+",
]


def _extract_company_from_search(result, evidence_id: str) -> dict[str, Any] | None:
    """Extract company information from a search result."""
    import re

    title = result.title or ""
    content = result.content or ""
    url = result.url

    # Try to extract company name from title
    name = title.split(" - ")[0].split(" | ")[0].strip()
    if not name or len(name) < 2:
        return None

    # Filter out non-company entries
    for pattern in _NON_COMPANY_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return None

    # Skip if the name looks like a person title rather than a company
    if re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+$", name) and not any(
        word in name.lower() for word in ["corp", "inc", "llc", "ltd", "tech", "soft", "lab", "hub", "stack"]
    ):
        # Could be a person name - only skip if content doesn't clearly indicate a company
        if not re.search(r"(?:company|corporation|inc\.|founded|headquarters|employees)", content.lower()):
            return None

    # Skip LinkedIn profiles, news articles, and blog posts masquerading as companies
    skip_domains = {"linkedin.com", "twitter.com", "facebook.com"}
    skip_title_words = {"at ", "leadership", "report", "landscape", "guide", "review", "list", "overview"}
    url_lower = url.lower()
    if any(d in url_lower for d in skip_domains):
        return None
    if any(w in name.lower() for w in skip_title_words):
        return None

    # Extract employee count
    employee_count = None
    emp_match = re.search(r"(?:approximately|about|over|~)?\s*(\d[\d,]*)\s*(?:\+?\s*)?(?:employee|staff|member|people)", content.lower())
    if emp_match:
        employee_count = int(emp_match.group(1).replace(",", ""))

    # Extract founded year
    founded = None
    founded_match = re.search(r"(?:founded|est\.?|established)\s*(?:in\s*)?(\d{4})", content, re.IGNORECASE)
    if founded_match:
        founded = founded_match.group(1)

    # Extract revenue
    revenue = None
    rev_match = re.search(r"(?:revenue|arr|annual recurring revenue)[:\s]*\$?([\d.]+)\s*(billion|million|b|m|bn|mn|k)?\+?", content, re.IGNORECASE)
    if rev_match:
        amount = rev_match.group(1)
        unit = rev_match.group(2) or ""
        revenue = f"${amount}{unit}"
    else:
        rev_match = re.search(r"\$([\d.]+)\s*(billion|million|b|m|bn|mn)\+?", content, re.IGNORECASE)
        if rev_match:
            revenue = f"${rev_match.group(1)}{rev_match.group(2)}"

    # Extract location
    location = None
    for country in ["india", "united states", "usa", "united kingdom", "uk"]:
        if country in content.lower():
            location = country.title() if country != "usa" else "United States"
            break

    # Extract city
    city = None
    city_match = re.search(r"(?:headquarters|headquartered|based in|city)[:\s]*([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", content)
    if city_match:
        city = city_match.group(1)

    # Extract industry
    industry = None
    content_lower = content.lower()
    for ind in ["saas", "fintech", "ecommerce", "e-commerce", "ai", "cloud", "devtools", "testing"]:
        if ind in content_lower or ind in title.lower():
            industry = ind.upper() if ind in ("saas", "ai") else ind.title()
            break

    # Extract domain from URL as website
    website = url
    website_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if website_match:
        website = website_match.group(1)

    return {
        "name": name,
        "website": website,
        "industry": industry,
        "location": location,
        "city": city,
        "employee_count": employee_count,
        "founded": founded,
        "revenue": revenue,
        "description": content[:300],
        "evidence_ids": [evidence_id],
    }


def _company_exists(companies: list[dict], name: str) -> bool:
    """Check if a company with this name already exists."""
    name_lower = name.lower()
    return any(c.get("name", "").lower() == name_lower for c in companies)
