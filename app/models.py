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
    quality_result_id: str = field(default_factory=lambda: f"dq_{uuid.uuid4().hex[:8]}")
    lead_id: str = ""
    research_job_id: str | None = None
    original_lead: dict[str, Any] = field(default_factory=dict)
    cleaned_lead: dict[str, Any] = field(default_factory=dict)
    validation: list[FieldValidation] = field(default_factory=list)
    duplicate_result: DuplicateResult = field(default_factory=DuplicateResult)
    issues: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality_result_id": self.quality_result_id,
            "lead_id": self.lead_id,
            "research_job_id": self.research_job_id,
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
            "created_at": self.created_at,
        }


@dataclass
class ConfidenceResult:
    """Output of the Confidence Engine."""
    confidence_result_id: str = field(default_factory=lambda: f"cr_{uuid.uuid4().hex[:8]}")
    lead_id: str = ""
    research_job_id: str | None = None
    quality_result_id: str | None = None
    score: int = 0  # 0-100
    level: str = "low"  # "high", "medium", "low"
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_result_id": self.confidence_result_id,
            "lead_id": self.lead_id,
            "research_job_id": self.research_job_id,
            "quality_result_id": self.quality_result_id,
            "score": self.score,
            "level": self.level,
            "positive_factors": self.positive_factors,
            "negative_factors": self.negative_factors,
            "conflicts": [
                {"field": c.field, "values": c.values}
                for c in self.conflicts
            ],
            "created_at": self.created_at,
        }


@dataclass
class ReviewItem:
    """An item in the review queue."""
    review_id: str = field(default_factory=lambda: f"review_{uuid.uuid4().hex[:8]}")
    lead_id: str = ""
    research_job_id: str | None = None
    reason: str = ""  # "medium_confidence", "low_confidence", "conflict", "possible_duplicate", "validation_failure"
    lead_data: dict[str, Any] = field(default_factory=dict)
    confidence_score: int = 0
    confidence_level: str = ""
    confidence_result_id: str | None = None
    quality_result_id: str | None = None
    issues: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    status: str = "pending"  # "pending", "approved", "rejected", "needs_more_research"
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "lead_id": self.lead_id,
            "research_job_id": self.research_job_id,
            "reason": self.reason,
            "lead_data": self.lead_data,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "confidence_result_id": self.confidence_result_id,
            "quality_result_id": self.quality_result_id,
            "issues": self.issues,
            "conflicts": self.conflicts,
            "evidence_refs": self.evidence_refs,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class DuplicateEvent:
    """Record of a duplicate detection event."""
    duplicate_event_id: str = field(default_factory=lambda: f"dup_{uuid.uuid4().hex[:8]}")
    incoming_lead_id: str = ""
    matched_master_id: str | None = None
    match_type: str = ""  # "exact", "probable"
    match_reason: str = ""  # "exact_email", "exact_linkedin", "same_domain_and_person"
    quality_result_id: str | None = None
    research_job_id: str | None = None
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "duplicate_event_id": self.duplicate_event_id,
            "incoming_lead_id": self.incoming_lead_id,
            "matched_master_id": self.matched_master_id,
            "match_type": self.match_type,
            "match_reason": self.match_reason,
            "quality_result_id": self.quality_result_id,
            "research_job_id": self.research_job_id,
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
    confidence_result_id: str | None = None
    review_id: str | None = None
    source_lead_json: dict[str, Any] = field(default_factory=dict)

    # Status
    status: str = "accepted"  # "accepted", "under_review", "merged", "archived"
    created_at: str = field(default_factory=lambda: date.today().isoformat())
    updated_at: str = field(default_factory=lambda: date.today().isoformat())

    # Phase 3: Assignment
    assigned_to: str | None = None  # UUID
    assigned_at: str | None = None
    assigned_by: str | None = None  # UUID

    # Phase 3: Pipeline
    pipeline_stage: str = "new"
    pipeline_stage_at: str = field(default_factory=lambda: date.today().isoformat())
    pipeline_changed_by: str | None = None  # UUID

    # Phase 3: Priority
    priority: str = "medium"  # "low", "medium", "high"

    # Phase 3: Next Action
    next_action_at: str | None = None
    next_action_type: str | None = None  # "call", "email", "meeting", "follow_up", "other"

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
            "confidence_result_id": self.confidence_result_id,
            "review_id": self.review_id,
            "source_lead_json": self.source_lead_json,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "assigned_at": self.assigned_at,
            "assigned_by": self.assigned_by,
            "pipeline_stage": self.pipeline_stage,
            "pipeline_stage_at": self.pipeline_stage_at,
            "pipeline_changed_by": self.pipeline_changed_by,
            "priority": self.priority,
            "next_action_at": self.next_action_at,
            "next_action_type": self.next_action_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# Phase 3: Users, Assignment, Pipeline, Activities
# ============================================================================


@dataclass
class AppUser:
    """Application user (identity layer, not full auth)."""
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""
    role: str = "bd"  # "admin", "manager", "bd"
    is_active: bool = True
    created_at: str = field(default_factory=lambda: date.today().isoformat())
    updated_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class AssignmentRecord:
    """Record of a lead assignment action."""
    assignment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    master_id: str = ""
    assigned_to: str = ""  # UUID
    assigned_by: str = ""  # UUID
    action: str = ""  # "assigned", "reassigned", "unassigned"
    reason: str | None = None
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "master_id": self.master_id,
            "assigned_to": self.assigned_to,
            "assigned_by": self.assigned_by,
            "action": self.action,
            "reason": self.reason,
            "created_at": self.created_at,
        }


@dataclass
class PipelineTransition:
    """Record of a pipeline stage change."""
    transition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    master_id: str = ""
    from_stage: str | None = None
    to_stage: str = ""
    changed_by: str | None = None  # UUID
    reason: str | None = None
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "master_id": self.master_id,
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "created_at": self.created_at,
        }


@dataclass
class Activity:
    """An audit trail entry for a lead."""
    activity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    master_id: str = ""
    activity_type: str = ""
    performed_by: str | None = None  # UUID
    title: str = ""
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "master_id": self.master_id,
            "activity_type": self.activity_type,
            "performed_by": self.performed_by,
            "title": self.title,
            "description": self.description,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
