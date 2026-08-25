"""Cleaning module — normalizes lead data without changing meaning."""

from __future__ import annotations

import re
from typing import Any


# Lead field names that map to Standard Lead JSON keys
_LEAD_FIELDS = {
    "company_name": "Company Name",
    "website": "Website",
    "industry": "Industry",
    "category": "Category",
    "segment": "Segment",
    "founded": "Founded",
    "revenue": "Revenue",
    "city_country": "City/Country",
    "ceo_founder_name": "Ceo/Founder Name",
    "ceo_linkedin": "CEO Linkedn",
    "marketing_head_name": "Marketing Head name",
    "marketing_head_linkedin": "Marketing Head Linkedn",
    "contact_email": "Contact email",
}


def clean_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Clean a Standard Lead dict. Returns a new dict; original is untouched."""
    cleaned = dict(lead)

    cleaned["company_name"] = _clean_company_name(cleaned.get("Company Name"))
    cleaned["website"] = _clean_website(cleaned.get("Website"))
    cleaned["industry"] = _clean_text(cleaned.get("Industry"))
    cleaned["category"] = _clean_text(cleaned.get("Category"))
    cleaned["segment"] = _clean_text(cleaned.get("Segment"))
    cleaned["founded"] = _clean_founded(cleaned.get("Founded"))
    cleaned["revenue"] = _clean_revenue(cleaned.get("Revenue"))
    cleaned["city_country"] = _clean_city_country(cleaned.get("City/Country"))
    cleaned["ceo_founder_name"] = _clean_person_name(cleaned.get("Ceo/Founder Name"))
    cleaned["ceo_linkedin"] = _clean_linkedin(cleaned.get("CEO Linkedn"))
    cleaned["marketing_head_name"] = _clean_person_name(cleaned.get("Marketing Head name"))
    cleaned["marketing_head_linkedin"] = _clean_linkedin(cleaned.get("Marketing Head Linkedn"))
    cleaned["contact_email"] = _clean_email(cleaned.get("Contact email"))
    cleaned["evidence_refs"] = cleaned.get("evidence_refs", [])
    cleaned["missing_fields"] = cleaned.get("missing_fields", [])

    return cleaned


def _clean_text(value: str | None) -> str | None:
    """Strip whitespace, normalize internal spaces, return None for empty."""
    if value is None:
        return None
    v = str(value).strip()
    v = re.sub(r"\s+", " ", v)
    if not v or v.lower() in ("null", "none", "n/a", "—", "-", "unknown"):
        return None
    return v


def _clean_company_name(value: str | None) -> str | None:
    """Clean company name: normalize whitespace, fix casing."""
    v = _clean_text(value)
    if v is None:
        return None
    # Remove common suffixes that add noise but preserve meaning
    v = re.sub(r"\s+", " ", v).strip()
    return v


def _clean_website(value: str | None) -> str | None:
    """Normalize website URL."""
    v = _clean_text(value)
    if v is None:
        return None
    # Add protocol if missing
    if not v.startswith(("http://", "https://")):
        v = "https://" + v
    # Remove trailing slash
    v = v.rstrip("/")
    # Remove www. prefix for consistency
    v = re.sub(r"https?://www\.", "https://", v)
    return v


def _clean_founded(value: str | None) -> str | None:
    """Normalize founded year."""
    v = _clean_text(value)
    if v is None:
        return None
    # Extract 4-digit year
    year_match = re.search(r"(\d{4})", v)
    if year_match:
        return year_match.group(1)
    return v


def _clean_revenue(value: str | None) -> str | None:
    """Normalize revenue string."""
    v = _clean_text(value)
    if v is None:
        return None
    # Remove trailing period
    v = v.rstrip(".")
    # Normalize dollar sign
    v = v.replace("$.", "$")
    if v == "$":
        return None
    return v


def _clean_person_name(value: str | None) -> str | None:
    """Normalize person name: title case, remove extra spaces."""
    v = _clean_text(value)
    if v is None:
        return None
    # Title case each word
    words = v.split()
    cleaned_words = []
    for word in words:
        # Preserve all-caps abbreviations (CEO, CTO, etc.)
        if word.isupper() and len(word) <= 4:
            cleaned_words.append(word)
        # Preserve hyphenated names
        elif "-" in word:
            parts = word.split("-")
            cleaned_words.append("-".join(p.capitalize() for p in parts))
        else:
            cleaned_words.append(word.capitalize())
    return " ".join(cleaned_words)


def _clean_linkedin(value: str | None) -> str | None:
    """Normalize LinkedIn URL."""
    v = _clean_text(value)
    if v is None:
        return None
    # Add protocol if missing
    if not v.startswith(("http://", "https://")):
        v = "https://" + v
    # Normalize linkedin.com/in/ format
    v = re.sub(r"https?://(www\.)?linkedin\.com", "https://www.linkedin.com", v)
    # Remove trailing slash
    v = v.rstrip("/")
    return v


def _clean_email(value: str | None) -> str | None:
    """Normalize email: lowercase, strip whitespace."""
    v = _clean_text(value)
    if v is None:
        return None
    return v.lower().strip()


def _clean_city_country(value: str | None) -> str | None:
    """Normalize city/country string."""
    v = _clean_text(value)
    if v is None:
        return None
    # Title case each part separated by comma
    parts = [p.strip().title() for p in v.split(",")]
    return ", ".join(parts)
