"""Node: Research Companies

Enriches company information by crawling their websites and gathering more details.
"""

from __future__ import annotations

from typing import Any

from app.evidence import search_result_to_evidence
from app.intelligence import IntelligenceProvider
from app.providers.firecrawl import FirecrawlProvider
from app.state import ResearchState


def create_research_companies_node(
    intelligence: IntelligenceProvider,
    firecrawl: FirecrawlProvider,
):
    """Create a node that enriches company information via crawling."""

    def research_companies(state: ResearchState) -> dict[str, Any]:
        companies: list[dict[str, Any]] = list(state.get("companies", []))
        evidence: list[dict[str, Any]] = list(state.get("evidence", []))

        enriched_companies: list[dict[str, Any]] = []
        for company in companies:
            website = company.get("website", "")
            if not website:
                enriched_companies.append(company)
                continue

            # Ensure URL has protocol
            url = website if website.startswith("http") else f"https://{website}"

            # Crawl the company website
            crawl_result = firecrawl.crawl(url)
            ev = search_result_to_evidence(crawl_result, entity=company.get("name"))
            ev_dict = ev.to_dict()
            evidence.append(ev_dict)

            # Merge crawl data into company record
            enriched = dict(company)
            enriched["evidence_ids"] = company.get("evidence_ids", []) + [ev.id]

            if crawl_result.content:
                enriched["description"] = crawl_result.content[:500]

                # Try to extract additional facts from crawl content
                import re
                content = crawl_result.content
                content_lower = content.lower()

                if not enriched.get("employee_count"):
                    emp_match = re.search(r"(?:approximately|about|over|~)?\s*(\d[\d,]*)\s*(?:\+?\s*)?(?:employee|staff|member|people)", content_lower)
                    if emp_match:
                        enriched["employee_count"] = int(emp_match.group(1).replace(",", ""))

                if not enriched.get("founded"):
                    founded_match = re.search(r"(?:founded|est\.?|established)\s*(?:in\s*)?(\d{4})", content, re.IGNORECASE)
                    if founded_match:
                        enriched["founded"] = founded_match.group(1)

                if not enriched.get("revenue"):
                    rev_match = re.search(r"(?:revenue|arr)[:\s]*\$?([\d.]+)\s*(billion|million|b|m|bn|mn|k)?\+?", content, re.IGNORECASE)
                    if rev_match:
                        enriched["revenue"] = f"${rev_match.group(1)}{rev_match.group(2)}"
                    else:
                        rev_match = re.search(r"\$([\d.]+)\s*(billion|million|b|m|bn|mn)\+?", content, re.IGNORECASE)
                        if rev_match:
                            enriched["revenue"] = f"${rev_match.group(1)}{rev_match.group(2)}"

                if not enriched.get("city"):
                    city_match = re.search(r"(?:headquarters|headquartered|based in|city)[:\s]*([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", content)
                    if city_match:
                        enriched["city"] = city_match.group(1)

                if not enriched.get("location"):
                    for country in ["india", "united states", "united kingdom", "canada"]:
                        if country in content_lower:
                            enriched["location"] = country.title()
                            break

            enriched_companies.append(enriched)

        log_entry = f"[research_companies] Enriched {len(enriched_companies)} companies via crawling"
        return {
            "companies": enriched_companies,
            "evidence": evidence,
            "log": state["log"] + [log_entry],
        }

    return research_companies
