"""Evidence management utilities.

Handles creating, storing, and indexing evidence from research results.
"""

from __future__ import annotations

from typing import Any

from app.models import Evidence, Fact, SearchResult


def search_result_to_evidence(result: SearchResult, entity: str | None = None) -> Evidence:
    """Convert a normalized SearchResult into an Evidence record."""
    facts = _extract_facts(result.content or "", entity)
    return Evidence(
        provider=result.provider,
        source_url=result.url,
        source_title=result.title,
        content=result.content,
        entity=entity or result.title,
        facts=facts,
    )


def evidence_to_dict(evidence: Evidence) -> dict[str, Any]:
    """Serialize an Evidence record to a plain dict for state storage."""
    return evidence.to_dict()


def extract_facts_from_text(text: str, entity: str | None = None) -> list[Fact]:
    """Extract simple facts from text. Uses keyword matching (mock approach).

    TODO: Replace with LLM-based extraction when intelligence provider is connected.
    """
    return _extract_facts(text, entity)


def _extract_facts(text: str, entity: str | None = None) -> list[Fact]:
    """Keyword-based fact extraction from text content."""
    import re

    facts: list[Fact] = []
    t = text.lower()

    # Employee count patterns
    emp_match = re.search(r"(?:approximately|about|over|~)?\s*(\d[\d,]*)\s*(?:\+?\s*)?(?:employee|staff|member|people)", t)
    if emp_match:
        facts.append(Fact(field="employee_count", value=emp_match.group(1).replace(",", "")))

    # Revenue patterns
    rev_match = re.search(r"\$([\d.]+)\s*(billion|million|b|m|bn|mn)\+?\s*(?:revenue|arr|annual|sales)?", t)
    if rev_match:
        facts.append(Fact(field="revenue", value=f"${rev_match.group(1)}{rev_match.group(2)}"))

    # IPO info
    if "ipo" in t or "publicly traded" in t or "nasdaq" in t or "nyse" in t:
        facts.append(Fact(field="is_public", value="true"))

    # Location patterns
    for country in ["india", "united states", "usa", "united kingdom", "uk", "canada", "germany"]:
        if country in t:
            facts.append(Fact(field="location", value=country.title()))
            break

    # Industry keywords
    for industry in ["saas", "fintech", "ecommerce", "e-commerce", "ai", "artificial intelligence", "cloud", "devtools", "api"]:
        if industry in t:
            facts.append(Fact(field="industry", value=industry.upper() if industry in ("saas", "ai", "api") else industry.title()))
            break

    # Title detection
    title_patterns = [
        (r"\b(cfo|chief financial officer)\b", "CFO"),
        (r"\b(cto|chief technology officer)\b", "CTO"),
        (r"\b(ceo|chief executive officer)\b", "CEO"),
        (r"\b(vp|vice president)\s+(finance|engineering|sales)\b", None),
        (r"\bhead of (finance|engineering|sales)\b", None),
    ]
    for pattern, fixed_title in title_patterns:
        title_match = re.search(pattern, t)
        if title_match:
            title = fixed_title or title_match.group(0).title()
            facts.append(Fact(field="person_title", value=title))
            break

    return facts
