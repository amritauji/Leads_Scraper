from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QualityIssue(BaseModel):
    field: str
    code: str
    severity: str
    message: str


class LeadQuality(BaseModel):
    """Data-quality metadata attached to a lead. Distinct from the Confidence score."""

    quality_score: float = Field(ge=0.0, le=1.0)
    is_valid: bool
    completeness: float = Field(ge=0.0, le=1.0)
    issues: list[QualityIssue] = Field(default_factory=list)
    duplicate_of: str | None = None
    merged_from: list[str] = Field(default_factory=list)
    merged_fields: list[str] = Field(default_factory=list)
    duplicate_reason: str | None = None


class QualityReport(BaseModel):
    """Batch-level summary emitted alongside the cleaned leads."""

    input_count: int
    output_count: int
    duplicate_count: int
    invalid_count: int
    error_count: int
    warning_count: int
    avg_quality_score: float
    details: dict[str, Any] = Field(default_factory=dict)
