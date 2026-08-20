from __future__ import annotations

from typing import Any

from . import fields as F
from .cleaning import clean_lead
from .dedup import detect_duplicates, merge_group
from .models import LeadQuality, QualityIssue, QualityReport
from .validation import ValidationResult, validate_lead

# quality_score = completeness * W_COMPLETE + validity * W_VALID
_W_COMPLETE = 0.6
_W_VALID = 0.4
_ERROR_PENALTY = 0.5
_WARNING_PENALTY = 0.1


def _completeness_score(lead: dict[str, Any]) -> float:
    total = sum(F.COMPLETENESS_WEIGHTS.values())
    got = sum(w for k, w in F.COMPLETENESS_WEIGHTS.items() if lead.get(k))
    return got / total if total else 0.0


def _validity_score(vr: ValidationResult) -> float:
    penalty = _ERROR_PENALTY * len(vr.errors) + _WARNING_PENALTY * len(vr.warnings)
    return max(0.0, 1.0 - penalty)


def _quality_score(lead: dict[str, Any], vr: ValidationResult) -> tuple[float, float]:
    completeness = _completeness_score(lead)
    validity = _validity_score(vr)
    score = round(_W_COMPLETE * completeness + _W_VALID * validity, 4)
    return score, round(completeness, 4)


def process_leads(
    leads: list[dict[str, Any]],
    existing_master: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], QualityReport]:
    """Run the full Data Quality Engine over a batch of Standard Lead dicts.

    Returns (clean_unique_leads, report). Each returned lead carries a
    'quality' block (LeadQuality.model_dump()). Deduplication runs across the
    incoming batch AND against existing_master when provided (the master rows
    are appended, deduped, then removed from the output so only *new* uniques
    are returned).
    """
    existing_master = existing_master or []
    master_offset = len(leads)

    # 1. Cleaning
    cleaned = [clean_lead(l) for l in leads] + [clean_lead(m) for m in existing_master]

    # 2. Validation (only on the incoming batch; master rows assumed already vetted)
    validations: list[ValidationResult] = []
    scores: list[float] = []
    completeness: list[float] = []
    for i, lead in enumerate(cleaned):
        if i < master_offset:
            vr = validate_lead(lead)
            s, c = _quality_score(lead, vr)
        else:
            vr = ValidationResult(is_valid=True, issues=[])
            s, c = _quality_score(lead, vr)
        validations.append(vr)
        scores.append(s)
        completeness.append(c)

    # 3. Duplicate detection + canonical merge
    groups, dup_to_canonical = detect_duplicates(cleaned, score_of=lambda i: scores[i])

    results: list[dict[str, Any]] = []
    duplicate_count = 0
    invalid_count = 0
    error_count = 0
    warning_count = 0

    for group in groups:
        canonical_idx = group.canonical_index
        merged = merge_group(cleaned, group, score_of=lambda i: scores[i])

        # Skip groups whose canonical belongs to the existing master (nothing new).
        if canonical_idx >= master_offset and all(m >= master_offset for m in group.member_indices):
            continue

        vr = validations[canonical_idx]
        merged_from = [
            cleaned[m].get(F.LEAD_ID) or f"idx_{m}"
            for m in group.member_indices
            if m != canonical_idx
        ]
        if merged_from:
            duplicate_count += len(merged_from)

        # recompute score after merge (merge fills nulls -> completeness can rise)
        post_vr = validate_lead(merged) if canonical_idx < master_offset else vr
        score, comp = _quality_score(merged, post_vr)

        if not post_vr.is_valid:
            invalid_count += 1
        error_count += len(post_vr.errors)
        warning_count += len(post_vr.warnings)

        quality = LeadQuality(
            quality_score=score,
            is_valid=post_vr.is_valid,
            completeness=comp,
            issues=[QualityIssue(field=i.field, code=i.code, severity=i.severity, message=i.message) for i in post_vr.issues],
            duplicate_of=None,
            merged_from=merged_from,
            merged_fields=sorted(group.merged_fields.keys()),
            duplicate_reason=group.reason if merged_from else None,
        )
        merged.pop("_norm", None)
        merged["quality"] = quality.model_dump()
        results.append(merged)

    avg = round(sum(r["quality"]["quality_score"] for r in results) / len(results), 4) if results else 0.0
    report = QualityReport(
        input_count=len(leads),
        output_count=len(results),
        duplicate_count=duplicate_count,
        invalid_count=invalid_count,
        error_count=error_count,
        warning_count=warning_count,
        avg_quality_score=avg,
        details={"master_size": len(existing_master)},
    )
    return results, report
