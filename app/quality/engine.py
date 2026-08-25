"""Data Quality Engine — combines cleaning, validation, and duplicate detection."""

from __future__ import annotations

from typing import Any

from app.models import (
    Conflict,
    DataQualityResult,
    DuplicateResult,
    FieldValidation,
)
from app.quality.cleaning import clean_lead
from app.quality.validation import validate_lead
from app.quality.duplicate import detect_duplicates


def run_quality_check(
    lead: dict[str, Any],
    existing_leads: list[dict[str, Any]] | None = None,
    lead_id: str | None = None,
    research_job_id: str | None = None,
) -> DataQualityResult:
    """Run full data quality pipeline on a Standard Lead JSON.

    Steps:
        1. Cleaning -- normalize text, URLs, names, emails
        2. Validation -- check field formats and completeness
        3. Duplicate Detection -- match against existing leads
        4. Conflict Detection -- find contradictory evidence

    Args:
        lead: Standard Lead JSON dict.
        existing_leads: Existing Lead Master records for dedup (optional).
        lead_id: Optional lead ID override.
        research_job_id: Optional research job ID for traceability.

    Returns:
        DataQualityResult with original, cleaned, validation, duplicates, issues, conflicts.
    """
    # Step 1: Clean
    cleaned = clean_lead(lead)

    # Step 2: Validate
    validation = validate_lead(cleaned)

    # Step 3: Duplicate detection
    dup_result = detect_duplicates(cleaned, existing_leads or [])

    # Step 4: Conflict detection
    conflicts = _detect_conflicts(lead, cleaned)

    # Aggregate issues
    issues: list[str] = []
    for v in validation:
        if v.status == "invalid":
            issues.extend(f"{v.field}: {i}" for i in v.issues)
        elif v.status == "missing":
            issues.extend(f"{v.field}: {i}" for i in v.issues)
    if dup_result.is_duplicate:
        issues.append(f"duplicate_detected: {dup_result.match_reason}")

    return DataQualityResult(
        lead_id=lead_id or lead.get("LeadId", ""),
        research_job_id=research_job_id,
        original_lead=lead,
        cleaned_lead=cleaned,
        validation=validation,
        duplicate_result=dup_result,
        issues=issues,
        conflicts=conflicts,
    )


def _detect_conflicts(original: dict[str, Any], cleaned: dict[str, Any]) -> list[Conflict]:
    """Detect conflicts between original values and cleaned values.

    Currently checks for significant disagreements between evidence sources
    by comparing the original lead's evidence-based fields.
    """
    conflicts: list[Conflict] = []

    # Check for conflicting person names (CEO vs Marketing Head sharing same name)
    ceo = cleaned.get("ceo_founder_name")
    mh = cleaned.get("marketing_head_name")
    if ceo and mh and ceo.lower() == mh.lower():
        conflicts.append(Conflict(
            field="person_name",
            values=[
                {"value": ceo, "evidence_id": "original_lead"},
                {"value": mh, "evidence_id": "original_lead"},
            ],
        ))

    # Check if industry/category conflict
    industry = cleaned.get("industry")
    category = cleaned.get("category")
    if industry and category and industry.lower() != category.lower():
        conflicts.append(Conflict(
            field="industry_category",
            values=[
                {"value": industry, "evidence_id": "industry_field"},
                {"value": category, "evidence_id": "category_field"},
            ],
        ))

    return conflicts
