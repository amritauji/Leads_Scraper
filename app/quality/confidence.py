"""Confidence Engine — rule-based scoring of lead quality."""

from __future__ import annotations

from typing import Any

from app.models import Conflict, ConfidenceResult, DataQualityResult


# Scoring rules — each returns (points, factor_name)
_SCORING_RULES: list[tuple[str, int, str]] = [
    # Positive factors
    ("valid_company_domain",    15, "valid_company_domain"),
    ("target_person_identified", 15, "target_person_identified"),
    ("professional_email_found", 15, "professional_email_found"),
    ("email_verified",          15, "email_verified"),
    ("multiple_sources",        10, "multiple_supporting_sources"),
    ("required_fields_complete", 10, "all_required_fields_present"),
    ("source_agreement",        10, "sources_agree_on_values"),
    ("linkedin_available",       5, "linkedin_profile_available"),
    ("founded_year_present",     3, "founded_year_provided"),
    ("revenue_present",          3, "revenue_data_provided"),

    # Negative factors
    ("missing_company_name",   -15, "company_name_missing"),
    ("missing_person_name",    -15, "decision_maker_missing"),
    ("invalid_email",          -20, "email_invalid_format"),
    ("missing_email",          -10, "email_not_found"),
    ("missing_website",        -10, "website_not_provided"),
    ("duplicate_detected",     -25, "possible_duplicate"),
    ("conflicting_data",       -10, "conflicting_information"),
    ("missing_linkedin",        -5, "linkedin_not_found"),
]

# Confidence level thresholds
_THRESHOLDS = {
    "high": 70,
    "medium": 40,
    "low": 0,
}


def calculate_confidence(
    dq_result: DataQualityResult,
    all_leads: list[dict[str, Any]] | None = None,
) -> ConfidenceResult:
    """Calculate confidence score for a lead based on data quality results.

    Args:
        dq_result: Output from Data Quality Engine.
        all_leads: Existing leads for duplicate check (optional).

    Returns:
        ConfidenceResult with score, level, factors, and conflicts.
    """
    cleaned = dq_result.cleaned_lead
    validation = dq_result.validation
    duplicate = dq_result.duplicate_result
    conflicts = dq_result.conflicts
    issues = dq_result.issues

    score = 0
    positive: list[str] = []
    negative: list[str] = []

    # --- Positive scoring ---

    # Valid company domain (website present + valid)
    website_valid = any(
        v.field == "Website" and v.status == "valid"
        for v in validation
    )
    if website_valid:
        score += 15
        positive.append("valid_company_domain")

    # Target person identified
    if cleaned.get("ceo_founder_name"):
        score += 15
        positive.append("target_person_identified")

    # Professional email found
    email_val = next((v for v in validation if v.field == "Contact email"), None)
    if email_val and email_val.status == "valid":
        score += 15
        positive.append("professional_email_found")

    # Email verified (from Hunter)
    if cleaned.get("contact_email"):
        # Check if any evidence has email_verified=True
        evidence_verified = any(
            "verified" in str(ref).lower()
            for ref in dq_result.original_lead.get("evidence_refs", [])
        )
        # Also check if email was marked verified in original lead
        if dq_result.original_lead.get("email_verified"):
            score += 15
            positive.append("email_verified")

    # Multiple supporting sources
    evidence_refs = cleaned.get("evidence_refs", [])
    if len(evidence_refs) >= 3:
        score += 10
        positive.append("multiple_supporting_sources")

    # Required fields complete
    required_fields = ["Company Name", "Ceo/Founder Name"]
    all_required_present = all(
        cleaned.get(f) or cleaned.get(_field_key(f))
        for f in required_fields
    )
    if all_required_present:
        score += 10
        positive.append("all_required_fields_present")

    # Source agreement (no conflicts)
    if not conflicts:
        score += 10
        positive.append("sources_agree_on_values")
    else:
        score -= 10
        negative.append("conflicting_information")

    # LinkedIn available
    if cleaned.get("ceo_linkedin") or cleaned.get("marketing_head_linkedin"):
        score += 5
        positive.append("linkedin_profile_available")
    else:
        score -= 5
        negative.append("linkedin_not_found")

    # Founded year
    if cleaned.get("founded"):
        score += 3
        positive.append("founded_year_provided")

    # Revenue
    if cleaned.get("revenue"):
        score += 3
        positive.append("revenue_data_provided")

    # --- Negative scoring ---

    # Missing company name
    if not cleaned.get("company_name"):
        score -= 15
        negative.append("company_name_missing")

    # Missing person name
    if not cleaned.get("ceo_founder_name"):
        score -= 15
        negative.append("decision_maker_missing")

    # Invalid email
    if email_val and email_val.status == "invalid":
        score -= 20
        negative.append("email_invalid_format")

    # Missing email
    if email_val and email_val.status == "missing":
        score -= 10
        negative.append("email_not_found")

    # Missing website
    website_val = next((v for v in validation if v.field == "Website"), None)
    if website_val and website_val.status in ("missing", "invalid"):
        score -= 10
        negative.append("website_not_provided")

    # Duplicate detected
    if duplicate.is_duplicate:
        score -= 25
        negative.append("possible_duplicate")

    # Conflicts reduce score
    if conflicts:
        score -= 10 * len(conflicts)

    # Clamp score to 0-100
    score = max(0, min(100, score))

    # Determine level
    level = "low"
    for threshold_level, threshold_value in sorted(_THRESHOLDS.items(), key=lambda x: -x[1]):
        if score >= threshold_value:
            level = threshold_level
            break

    # Override: conflicts always at least "low"
    if conflicts and level not in ("low",):
        level = "low"

    return ConfidenceResult(
        score=score,
        level=level,
        positive_factors=positive,
        negative_factors=negative,
        conflicts=conflicts,
    )


def _field_key(display_name: str) -> str:
    """Map display field name to internal key."""
    mapping = {
        "Company Name": "company_name",
        "Ceo/Founder Name": "ceo_founder_name",
        "Contact email": "contact_email",
        "Website": "website",
        "Industry": "industry",
        "Founded": "founded",
        "Revenue": "revenue",
        "City/Country": "city_country",
    }
    return mapping.get(display_name, display_name)
