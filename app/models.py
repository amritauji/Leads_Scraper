"""Normalized data structures for the research engine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from datetime import date


@dataclass
class SearchResult:
    """Normalized search result from any provider."""
    title: str | None = None
    url: str = ""
    content: str | None = None
    provider: str = ""


@dataclass
class CompanyCandidate:
    """A company identified during research."""
    name: str
    website: str | None = None
    industry: str | None = None
    location: str | None = None
    employee_count: int | None = None
    founded: str | None = None
    revenue: str | None = None
    city: str | None = None
    description: str | None = None
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class PersonCandidate:
    """A person identified during research."""
    name: str
    title: str | None = None
    role: str | None = None  # "ceo_founder" or "marketing_head"
    company_name: str | None = None
    linkedin_url: str | None = None
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ContactCandidate:
    """Contact information for a person."""
    person_name: str
    company_name: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    phone: str | None = None
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Fact:
    """A single extracted fact from evidence."""
    field: str
    value: str


@dataclass
class Evidence:
    """Research evidence collected from providers."""
    id: str = field(default_factory=lambda: f"evidence_{uuid.uuid4().hex[:8]}")
    provider: str = ""
    source_url: str = ""
    source_title: str | None = None
    content: str | None = None
    entity: str | None = None
    facts: list[Fact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "content": self.content,
            "entity": self.entity,
            "facts": [{"field": f.field, "value": f.value} for f in self.facts],
        }


@dataclass
class ResearchCriteria:
    """Structured interpretation of a research request."""
    company: dict[str, Any] = field(default_factory=dict)
    person: dict[str, Any] = field(default_factory=dict)
    raw_request: str = ""


@dataclass
class ResearchPlanStep:
    """A single step in the research plan."""
    step: str
    goal: str


@dataclass
class StandardLead:
    """Final lead output matching the required template.

    Fields: LeadId, Date, Category, Segment, Industry, Company Name,
    Website, Founded, Revenue, City/Country, Ceo/Founder Name,
    CEO Linkedn, Marketing Head name, Marketing Head Linkedn, Contact email
    """
    lead_id: str = field(default_factory=lambda: f"lead_{uuid.uuid4().hex[:8]}")
    date: str = field(default_factory=lambda: date.today().isoformat())
    category: str | None = None
    segment: str | None = None
    industry: str | None = None
    company_name: str | None = None
    website: str | None = None
    founded: str | None = None
    revenue: str | None = None
    city_country: str | None = None
    ceo_founder_name: str | None = None
    ceo_linkedin: str | None = None
    marketing_head_name: str | None = None
    marketing_head_linkedin: str | None = None
    contact_email: str | None = None
    evidence_refs: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "LeadId": self.lead_id,
            "Date": self.date,
            "Category": self.category,
            "Segment": self.segment,
            "Industry": self.industry,
            "Company Name": self.company_name,
            "Website": self.website,
            "Founded": self.founded,
            "Revenue": self.revenue,
            "City/Country": self.city_country,
            "Ceo/Founder Name": self.ceo_founder_name,
            "CEO Linkedn": self.ceo_linkedin,
            "Marketing Head name": self.marketing_head_name,
            "Marketing Head Linkedn": self.marketing_head_linkedin,
            "Contact email": self.contact_email,
            "evidence_refs": self.evidence_refs,
            "missing_fields": self.missing_fields,
        }


# ============================================================================
# Phase 2: Data Quality Engine, Confidence Engine, Review Queue, Lead Master
# ============================================================================


@dataclass
class FieldValidation:
    """Validation result for a single field."""
    field: str
    value: str | None
    status: str  # "valid", "invalid", "missing"
    issues: list[str] = field(default_factory=list)


@dataclass
class DuplicateResult:
    """Result of duplicate detection check."""
    is_duplicate: bool = False
    duplicate_type: str | None = None  # "exact", "probable", None
    matched_lead_id: str | None = None
    match_reason: str | None = None  # "exact_email", "exact_linkedin", "same_domain_person"


@dataclass
class Conflict:
    """A conflict between evidence sources."""
    field: str
    values: list[dict[str, Any]] = field(default_factory=list)  # [{value, evidence_id}]


@dataclass
class DataQualityResult:
    """Output of the Data Quality Engine for a single lead."""
    original_lead: dict[str, Any] = field(default_factory=dict)
    cleaned_lead: dict[str, Any] = field(default_factory=dict)
    validation: list[FieldValidation] = field(default_factory=list)
    duplicate_result: DuplicateResult = field(default_factory=DuplicateResult)
    issues: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_lead": self.original_lead,
            "cleaned_lead": self.cleaned_lead,
            "validation": [
                {"field": v.field, "value": v.value, "status": v.status, "issues": v.issues}
                for v in self.validation
            ],
            "duplicate_result": {
                "is_duplicate": self.duplicate_result.is_duplicate,
                "duplicate_type": self.duplicate_result.duplicate_type,
                "matched_lead_id": self.duplicate_result.matched_lead_id,
                "match_reason": self.duplicate_result.match_reason,
            },
            "issues": self.issues,
            "conflicts": [
                {"field": c.field, "values": c.values}
                for c in self.conflicts
            ],
        }


@dataclass
class ConfidenceResult:
    """Output of the Confidence Engine."""
    score: int = 0  # 0-100
    level: str = "low"  # "high", "medium", "low", "conflict"
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "positive_factors": self.positive_factors,
            "negative_factors": self.negative_factors,
            "conflicts": [
                {"field": c.field, "values": c.values}
                for c in self.conflicts
            ],
        }


@dataclass
class ReviewItem:
    """An item in the review queue."""
    review_id: str = field(default_factory=lambda: f"review_{uuid.uuid4().hex[:8]}")
    lead_id: str = ""
    reason: str = ""  # "low_confidence", "conflict", "invalid_fields", "duplicate", "missing_fields"
    lead_data: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    status: str = "pending"  # "pending", "approved", "rejected", "needs_more_research"
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "lead_id": self.lead_id,
            "reason": self.reason,
            "lead_data": self.lead_data,
            "confidence": self.confidence,
            "issues": self.issues,
            "conflicts": self.conflicts,
            "evidence_refs": self.evidence_refs,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class LeadMaster:
    """Authoritative accepted lead record in Lead Master."""
    master_id: str = field(default_factory=lambda: f"master_{uuid.uuid4().hex[:8]}")
    lead_id: str = ""  # Original Standard Lead ID
    research_job_id: str | None = None

    # Core fields (cleaned + validated)
    company_name: str | None = None
    website: str | None = None
    industry: str | None = None
    category: str | None = None
    segment: str | None = None
    founded: str | None = None
    revenue: str | None = None
    city_country: str | None = None

    # People
    ceo_founder_name: str | None = None
    ceo_linkedin: str | None = None
    marketing_head_name: str | None = None
    marketing_head_linkedin: str | None = None
    contact_email: str | None = None

    # Quality metadata
    confidence_score: int = 0
    confidence_level: str = "low"
    data_quality_issues: list[str] = field(default_factory=list)

    # Traceability
    evidence_refs: list[str] = field(default_factory=list)
    raw_evidence_refs: list[str] = field(default_factory=list)
    quality_result_id: str | None = None
    review_id: str | None = None
    source_lead_json: dict[str, Any] = field(default_factory=dict)

    # Status
    status: str = "accepted"  # "accepted", "under_review", "merged"
    created_at: str = field(default_factory=lambda: date.today().isoformat())
    updated_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "master_id": self.master_id,
            "lead_id": self.lead_id,
            "research_job_id": self.research_job_id,
            "company_name": self.company_name,
            "website": self.website,
            "industry": self.industry,
            "category": self.category,
            "segment": self.segment,
            "founded": self.founded,
            "revenue": self.revenue,
            "city_country": self.city_country,
            "ceo_founder_name": self.ceo_founder_name,
            "ceo_linkedin": self.ceo_linkedin,
            "marketing_head_name": self.marketing_head_name,
            "marketing_head_linkedin": self.marketing_head_linkedin,
            "contact_email": self.contact_email,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "data_quality_issues": self.data_quality_issues,
            "evidence_refs": self.evidence_refs,
            "raw_evidence_refs": self.raw_evidence_refs,
            "quality_result_id": self.quality_result_id,
            "review_id": self.review_id,
            "source_lead_json": self.source_lead_json,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
