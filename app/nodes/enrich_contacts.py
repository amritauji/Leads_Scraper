"""Node: Enrich Contacts

Finds professional email addresses using Hunter.io for identified people.
"""

from __future__ import annotations

from typing import Any

from app.intelligence import IntelligenceProvider
from app.providers.hunter import HunterProvider
from app.state import ResearchState


def create_enrich_contacts_node(
    intelligence: IntelligenceProvider,
    hunter: HunterProvider,
):
    """Create a node that discovers contact information."""

    def enrich_contacts(state: ResearchState) -> dict[str, Any]:
        companies = state.get("companies", [])
        people = state.get("people", [])
        contacts: list[dict[str, Any]] = list(state.get("contacts", []))
        evidence: list[dict[str, Any]] = list(state.get("evidence", []))

        # Limit Hunter calls to conserve free-tier credits
        max_hunter_calls = 2
        hunter_calls = 0

        # Build contacts from people + company domains (max N calls)
        for person in people:
            if hunter_calls >= max_hunter_calls:
                break

            company_name = person.get("company_name", "")
            person_name = person.get("name", "")
            website = None

            # Find matching company website
            for company in companies:
                cname = company.get("name") or ""
                if cname.lower() == company_name.lower():
                    website = company.get("website", "")
                    break

            if not website:
                continue

            # Use Hunter to find email
            contact = hunter.find_email(website, person_name)
            hunter_calls += 1
            contact_dict = {
                "person_name": contact.person_name,
                "company_name": contact.company_name,
                "email": contact.email,
                "email_verified": contact.email_verified,
                "phone": contact.phone,
                "evidence_ids": [],
            }

            # Avoid duplicates
            if not _contact_exists(contacts, contact_dict.get("email", "")):
                contacts.append(contact_dict)

        log_entry = f"[enrich_contacts] Found {len(contacts)} contact records ({hunter_calls} Hunter calls)"
        return {
            "contacts": contacts,
            "evidence": evidence,
            "log": state["log"] + [log_entry],
        }

    return enrich_contacts


def _contact_exists(contacts: list[dict], email: str) -> bool:
    """Check if this email already exists in contacts."""
    email_lower = email.lower()
    return any(c.get("email", "").lower() == email_lower for c in contacts if email)
