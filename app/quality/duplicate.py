"""Duplicate Detection module — deterministic matching rules."""

from __future__ import annotations

import re
from typing import Any

from app.models import DuplicateResult


def detect_duplicates(
    lead: dict[str, Any],
    existing_leads: list[dict[str, Any]],
) -> DuplicateResult:
    """Check if a lead duplicates any existing Lead Master record.

    Args:
        lead: Cleaned lead dict (internal keys like "company_name", "contact_email").
        existing_leads: List of existing Lead Master dicts.

    Returns:
        DuplicateResult with match info.
    """
    if not existing_leads:
        return DuplicateResult(is_duplicate=False)

    lead_email = _normalize_email(lead.get("contact_email"))
    lead_linkedin = _normalize_linkedin(lead.get("ceo_linkedin") or lead.get("marketing_head_linkedin"))
    lead_domain = _extract_domain(lead.get("website"))
    lead_company = _normalize_company(lead.get("company_name"))
    lead_ceo = _normalize_name(lead.get("ceo_founder_name"))
    lead_mh = _normalize_name(lead.get("marketing_head_name"))

    for existing in existing_leads:
        # Rule 1: Exact email match → definite duplicate
        if lead_email:
            ex_email = _normalize_email(existing.get("contact_email"))
            if ex_email and lead_email == ex_email:
                return DuplicateResult(
                    is_duplicate=True,
                    duplicate_type="exact",
                    matched_lead_id=existing.get("master_id") or existing.get("LeadId"),
                    match_reason="exact_email",
                )

        # Rule 2: Exact LinkedIn URL match → definite duplicate
        if lead_linkedin:
            ex_linkedin = _normalize_linkedin(
                existing.get("ceo_linkedin") or existing.get("CEO Linkedn")
                or existing.get("marketing_head_linkedin") or existing.get("Marketing Head Linkedn")
            )
            if ex_linkedin and lead_linkedin == ex_linkedin:
                return DuplicateResult(
                    is_duplicate=True,
                    duplicate_type="exact",
                    matched_lead_id=existing.get("master_id") or existing.get("LeadId"),
                    match_reason="exact_linkedin",
                )

        # Rule 3: Same domain + same person name → probable duplicate
        if lead_domain and lead_ceo:
            ex_domain = _extract_domain(existing.get("website") or existing.get("Website"))
            ex_ceo = _normalize_name(existing.get("ceo_founder_name") or existing.get("Ceo/Founder Name"))
            if ex_domain and ex_ceo and lead_domain == ex_domain and lead_ceo == ex_ceo:
                return DuplicateResult(
                    is_duplicate=True,
                    duplicate_type="probable",
                    matched_lead_id=existing.get("master_id") or existing.get("LeadId"),
                    match_reason="same_domain_person",
                )

        # Rule 4: Same domain + same marketing head → probable duplicate
        if lead_domain and lead_mh:
            ex_domain = _extract_domain(existing.get("website") or existing.get("Website"))
            ex_mh = _normalize_name(existing.get("marketing_head_name") or existing.get("Marketing Head name"))
            if ex_domain and ex_mh and lead_domain == ex_domain and lead_mh == ex_mh:
                return DuplicateResult(
                    is_duplicate=True,
                    duplicate_type="probable",
                    matched_lead_id=existing.get("master_id") or existing.get("LeadId"),
                    match_reason="same_domain_person",
                )

    return DuplicateResult(is_duplicate=False)


def _normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return str(email).lower().strip()


def _normalize_linkedin(url: str | None) -> str | None:
    if not url:
        return None
    v = str(url).lower().strip().rstrip("/")
    v = re.sub(r"https?://(www\.)?linkedin\.com", "https://www.linkedin.com", v)
    return v


def _extract_domain(website: str | None) -> str | None:
    if not website:
        return None
    v = str(website).lower().strip()
    v = re.sub(r"https?://", "", v)
    v = re.sub(r"/.*$", "", v)
    v = re.sub(r"^www\.", "", v)
    v = v.rstrip("/")
    return v if v else None


def _normalize_company(name: str | None) -> str | None:
    if not name:
        return None
    return str(name).lower().strip()


def _normalize_name(name: str | None) -> str | None:
    if not name:
        return None
    return str(name).lower().strip()
