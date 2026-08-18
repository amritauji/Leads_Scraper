"""Lead builder utilities.

Converts collected evidence and entities into flat Standard Lead JSON.
"""

from __future__ import annotations

from typing import Any

from app.intelligence import IntelligenceProvider


def build_leads(
    intelligence: IntelligenceProvider,
    criteria: dict[str, Any],
    companies: list[dict[str, Any]],
    people: list[dict[str, Any]],
    contacts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build Standard Lead JSON from collected data.

    Returns a list of flat lead dicts matching the required template.
    """
    if not companies:
        return []

    leads: list[dict[str, Any]] = []

    for i, company in enumerate(companies):
        company_name = company.get("name", "")

        # Find matching people for this company
        company_people = [p for p in people if p.get("company_name", "").lower() == company_name.lower()]

        # Find matching contact for this company
        company_contact = None
        for c in contacts:
            if c.get("company_name", "").lower() == company_name.lower():
                company_contact = c
                break
        if not company_contact and contacts:
            company_contact = contacts[0] if i >= len(contacts) else contacts[i] if i < len(contacts) else None

        lead = intelligence.build_lead(
            criteria=criteria,
            companies=[company],
            people=company_people,
            contacts=[company_contact] if company_contact else [],
            evidence=evidence,
        )
        leads.append(lead)

    return leads
